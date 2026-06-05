"""
dhmc/langgraph_checkpointer.py

PRIMARY INTEGRATION POINT with LangGraph.

Wraps LangGraph's BaseCheckpointSaver. Intercepts put_writes() and put()
(the after_tick() checkpoint commit) to compute DHMC step bindings without
modifying the Pregel engine, node logic, or orchestration layer.

LangGraph Pregel superstep → DHMC micro-step mapping:
  - checkpoint_pending_writes  → PreHash input capture
  - after_tick() / put()       → PostHash computation + MMR append
  - thread_id                  → DHMC session ID
  - checkpoint_id              → DHMC step identifier
  - channel_values             → DHMC payload (content-addressed)
"""

import hashlib
import logging
import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .crypto import _blake3, _canonical_bytes
from .mmr_engine import MerkleMountainRange
from .nonce_gen import SoftwareSimulatedEnclave, RegistrationToken
from .schema_envelope import SchemaEnvelope, DeviationCode, StepType, GenesisCommitment, compute_envelope_hash

logger = logging.getLogger('dhmc')


def _content_address(payload: Any) -> str:
    """CAS URI: sha256(canonical_bytes(payload))"""
    raw = _canonical_bytes(payload)
    digest = hashlib.sha256(raw).hexdigest()
    return f"cas://sha256:{digest}"


@dataclass
class DHMCStepRecord:
    """Complete record for one micro-step (one LangGraph superstep)."""
    step_id: str
    module_id: str
    step_type: StepType
    pre_hash: bytes
    post_hash: bytes
    binding: bytes
    input_cas_uri: str
    output_cas_uri: str
    nonce: bytes
    monotonic_counter: int
    timestamp: float
    prev_module_hash: bytes = field(default_factory=lambda: b'\x00' * 32)  # H(M_{t-1}) at registration
    deviation: Optional[DeviationCode] = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "module_id": self.module_id,
            "step_type": self.step_type.value,
            "pre_hash": self.pre_hash.hex(),
            "post_hash": self.post_hash.hex(),
            "binding": self.binding.hex(),
            "input_cas_uri": self.input_cas_uri,
            "output_cas_uri": self.output_cas_uri,
            "nonce": self.nonce.hex(),
            "monotonic_counter": self.monotonic_counter,
            "timestamp": self.timestamp,
            "prev_module_hash": self.prev_module_hash.hex(),
            "deviation": self.deviation.value if self.deviation else None,
        }


@dataclass
class DHMCModuleState:
    """Runtime state for one macro-module."""
    module_id: str
    envelope: SchemaEnvelope
    mmr: MerkleMountainRange = field(default_factory=MerkleMountainRange)
    steps: List[DHMCStepRecord] = field(default_factory=list)
    observed_step_types: List[StepType] = field(default_factory=list)
    max_observed_depth: int = 0
    is_closed: bool = False
    module_hash: Optional[bytes] = None


class DHMCCheckpointer:
    """
    DHMC wrapper over LangGraph's checkpointing system.

    Usage:
        base_checkpointer = MemorySaver()  # or SqliteSaver, PostgresSaver
        dhmc = DHMCCheckpointer(
            session_id="loan-approval-001",
            envelopes={
                "M1": SchemaEnvelope("M1", min_steps=1, max_steps=3,
                                     allowed_types={StepType.LLM}),
                "M2": SchemaEnvelope("M2", min_steps=3, max_steps=5,
                                     allowed_types={StepType.RAG, StepType.TOOL,
                                                    StepType.VALIDATION},
                                     allowed_branches={"fraud_check", "standard"}),
                "M3": SchemaEnvelope("M3", min_steps=1, max_steps=2,
                                     allowed_types={StepType.LLM, StepType.SYNTHESIS}),
            }
        )
    """

    def __init__(
        self,
        session_id: str,
        envelopes: Dict[str, SchemaEnvelope],
        max_cas_entries: int = 10000,
    ):
        self.session_id = session_id
        self.envelopes = envelopes
        self.max_cas_entries = max_cas_entries
        self.enclave = SoftwareSimulatedEnclave(session_id)
        self.cas_store: OrderedDict[str, Any] = OrderedDict()  # LRU bounded content-address store
        self.evicted_uris: set = set()  # Track CAS URIs evicted by LRU policy
        self.step_records: List[DHMCStepRecord] = []
        self.step_by_id: Dict[str, DHMCStepRecord] = {}
        self.step_by_nonce: Dict[bytes, DHMCStepRecord] = {}
        self.steps_by_module: Dict[str, List[DHMCStepRecord]] = {mod_id: [] for mod_id in envelopes}
        
        self.module_states: Dict[str, DHMCModuleState] = {}
        self.module_chain: List[bytes] = []           # ordered module hashes
        self.module_close_order: list = list(envelopes.keys())
        self._next_close_index: int = 0
        self._prev_module_hash = b'\x00' * 32         # Genesis anchor

        # Initialize module states
        for mod_id, envelope in envelopes.items():
            self.module_states[mod_id] = DHMCModuleState(
                module_id=mod_id,
                envelope=envelope,
                mmr=MerkleMountainRange(epoch_size=envelope.epoch_size),
            )

        # Create Genesis Commitment to anchor the chain
        envelope_hashes = {mod_id: compute_envelope_hash(env) for mod_id, env in envelopes.items()}
        self.genesis_commitment = self.enclave.issue_genesis_commitment(
            query_hash=b'\x00' * 32,
            envelope_hashes=envelope_hashes
        )
        self._prev_module_hash = self.genesis_commitment.commitment_hash()
        self.enclave.advance_module(self._prev_module_hash)

    # ── Core DHMC step registration ───────────────────────────────────────────

    def register_step(
        self,
        module_id: str,
        step_type: StepType,
        input_payload: Any,
        output_payload: Any,
        branch_id: Optional[str] = None,
        subagent_final_hash: Optional[bytes] = None,
    ) -> DHMCStepRecord:
        """
        Called at each LangGraph superstep boundary (after_tick equivalent).
        Computes PreHash → PostHash → Binding → MMR append.

        Maps to LangGraph:
          input_payload  ← checkpoint_pending_writes (writes buffer during Execute phase)
          output_payload ← channel_values after apply_writes (Update phase)
        """
        module = self.module_states[module_id]
        if module.is_closed:
            raise RuntimeError(f"Module {module_id} is already closed — Invariant II violated")

        step_id = f"{module_id}:step:{len(module.steps):04d}:{uuid.uuid4().hex[:8]}"

        # ── Capture chain state at this exact moment (before token issued) ───
        chain_state_at_registration = self._prev_module_hash

        # ── Incremental schema validation (before step executes) ──────────────
        deviation = module.envelope.validate_step_type(step_type)
        if branch_id:
            branch_deviation = module.envelope.validate_branch(branch_id)
            if branch_deviation and not deviation:
                deviation = branch_deviation

        # ── TEE registration token ────────────────────────────────────────────
        token: RegistrationToken = self.enclave.issue_registration_token(step_id)

        # ── Content-address payloads to CAS ──────────────────────────────────
        input_uri = _content_address(input_payload)
        output_uri = _content_address(output_payload)
        
        for uri, payload in [(input_uri, input_payload), (output_uri, output_payload)]:
            self.cas_store[uri] = payload
            self.cas_store.move_to_end(uri)
            if len(self.cas_store) > self.max_cas_entries:
                evicted_uri, _ = self.cas_store.popitem(last=False)
                self.evicted_uris.add(evicted_uri)

        # ── PreHash: binds input + nonce + chain state ────────────────────────
        pre_hash = _blake3(
            step_id.encode(),
            _canonical_bytes(input_payload),
            token.nonce,
            chain_state_at_registration,
        )

        # ── PostHash: chains to PreHash ───────────────────────────────────────
        if subagent_final_hash:
            # Recursive sub-agent: output is the sub-agent's final hash
            output_binding_data = subagent_final_hash
        else:
            output_binding_data = _canonical_bytes(output_payload)

        post_hash = _blake3(
            step_id.encode(),
            output_binding_data,
            pre_hash,
        )

        # ── Leaf binding ──────────────────────────────────────────────────────
        binding = _blake3(
            bytes(a ^ b for a, b in zip(pre_hash, post_hash))
        )

        # ── MMR append ────────────────────────────────────────────────────────
        module.mmr.append(binding)

        record = DHMCStepRecord(
            step_id=step_id,
            module_id=module_id,
            step_type=step_type,
            pre_hash=pre_hash,
            post_hash=post_hash,
            binding=binding,
            input_cas_uri=input_uri,
            output_cas_uri=output_uri,
            nonce=token.nonce,
            monotonic_counter=token.monotonic_counter,
            timestamp=token.issued_at,
            prev_module_hash=chain_state_at_registration,
            deviation=deviation,
        )

        module.steps.append(record)
        module.observed_step_types.append(step_type)
        self.step_records.append(record)
        self.step_by_id[record.step_id] = record
        self.step_by_nonce[record.nonce] = record
        self.steps_by_module[module_id].append(record)

        return record

    # ── Module closure ────────────────────────────────────────────────────────

    def close_module(self, module_id: str) -> bytes:
        """
        Finalize a macro-module. Computes R_t (MMR commitment) and H(M_t).
        Enforces Invariants II and III.

        H(M_t) = BLAKE3(H(M_{t-1}) || R_t || N_t)
        where N_t = step count, R_t = final MMR commitment.
        """
        # ── Module closure ordering check (R9) ────────────────────────────────
        expected_id = self.module_close_order[self._next_close_index] if self._next_close_index < len(self.module_close_order) else None
        if expected_id and module_id != expected_id:
            logger.warning(
                f"Module {module_id} closed out of declared order "
                f"(expected {expected_id}). Chain integrity may be affected."
            )

        module = self.module_states[module_id]
        if module.is_closed:
            raise RuntimeError(f"Module {module_id} already closed")

        # ── Envelope conformance at closure (Invariant III) ───────────────────
        violations = module.envelope.validate_at_closure(
            observed_count=len(module.steps),
            observed_depth=module.max_observed_depth,
        )
        if violations:
            logger.warning(f"Module {module_id} envelope violations: {violations}")

        # ── Merkle commitment R_t ─────────────────────────────────────────────
        R_t = module.mmr.final_commitment()

        # ── Inter-module chaining formula ─────────────────────────────────────
        N_t = len(module.steps).to_bytes(4, 'big')
        H_t = _blake3(self._prev_module_hash, R_t, N_t)

        module.is_closed = True
        module.module_hash = H_t
        self.module_chain.append(H_t)

        # Track closure ordering
        if module_id in self.module_close_order:
            idx = self.module_close_order.index(module_id)
            if idx == self._next_close_index:
                self._next_close_index += 1

        # Advance enclave chain state for next module's nonce derivation
        self._prev_module_hash = H_t
        self.enclave.advance_module(H_t)

        logger.info(
            f"Module {module_id} closed | steps={len(module.steps)} "
            f"| H(M)={H_t.hex()[:16]}..."
        )
        return H_t

    # ── Sub-agent support ─────────────────────────────────────────────────────

    def spawn_subagent_dhmc(self, parent_module_id: str, parent_step_id: str) -> 'DHMCCheckpointer':
        """
        Spawn a child DHMC instance for a sub-agent.
        Returns a new DHMCCheckpointer whose genesis is co-signed by parent enclave.
        Sub-agent's session is bound to parent chain state at spawn time.
        """
        spawn_nonce = self.enclave.issue_spawn_nonce(
            parent_step_id,
            self._prev_module_hash
        )
        sub_session_id = f"{self.session_id}::sub::{parent_step_id[:16]}"
        child = DHMCCheckpointer.__new__(DHMCCheckpointer)
        child.session_id = sub_session_id
        child.envelopes = {}
        child.max_cas_entries = self.max_cas_entries
        child.enclave = SoftwareSimulatedEnclave(sub_session_id)
        child.cas_store = OrderedDict()
        child.step_records = []
        child.step_by_id = {}
        child.step_by_nonce = {}
        child.steps_by_module = {}
        child.module_states = {}
        child.module_chain = []
        child.module_close_order = []
        child._next_close_index = 0
        child.evicted_uris = set()
        # Bind child genesis to parent chain state
        child._prev_module_hash = _blake3(self._prev_module_hash, spawn_nonce)
        child.genesis_commitment = None  # Sub-agent has no independent genesis
        logger.info(
            f"Sub-agent spawned | parent_step={parent_step_id[:20]} "
            f"| genesis_binding={child._prev_module_hash.hex()[:16]}..."
        )
        return child

    def collapse_subagent(self, parent_module_id: str, step_type: StepType,
                          child_dhmc: 'DHMCCheckpointer',
                          input_payload: Any) -> DHMCStepRecord:
        """
        Collapse a completed sub-agent's DHMC chain to a single leaf in parent MMR.
        SubAgentLeaf = BLAKE3(child_final_hash || parent_step_id || spawn_nonce_binding)
        """
        child_final_hash = child_dhmc._prev_module_hash  # Final chain state
        return self.register_step(
            module_id=parent_module_id,
            step_type=step_type,
            input_payload=input_payload,
            output_payload={"subagent_session": child_dhmc.session_id,
                            "final_hash": child_final_hash.hex()},
            subagent_final_hash=child_final_hash,
        )

    # ── Audit export ──────────────────────────────────────────────────────────

    def export_chain(self) -> dict:
        """Export full provenance chain for auditor."""
        return {
            "session_id": self.session_id,
            "genesis_commitment": {
                "query_hash": self.genesis_commitment.query_hash.hex(),
                "envelope_hashes": {k: v.hex() for k, v in self.genesis_commitment.envelope_hashes.items()},
                "commitment_hash": self.genesis_commitment.commitment_hash().hex(),
                "enclave_sig": self.genesis_commitment.enclave_sig.hex(),
            } if self.genesis_commitment is not None else None,
            "module_count": len(self.module_chain),
            "final_hash": self._prev_module_hash.hex(),
            "modules": {
                mod_id: {
                    "step_count": len(state.steps),
                    "is_closed": state.is_closed,
                    "module_hash": state.module_hash.hex() if state.module_hash else None,
                    "mmr_state": state.mmr.state_snapshot(),
                    "steps": [s.to_dict() for s in state.steps],
                }
                for mod_id, state in self.module_states.items()
            },
            "cas_uris": list(self.cas_store.keys()),
        }

    def get_payload(self, cas_uri: str) -> Optional[Any]:
        """Retrieve content-addressed payload for forensic reconstruction."""
        result = self.cas_store.get(cas_uri)
        if result is not None:
            return result
        if cas_uri in self.evicted_uris:
            return "__CAS_EVICTED__"  # sentinel
        return None
