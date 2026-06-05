"""
dhmc/schema_envelope.py
Schema-envelope pre-commitment and validation.

Replaces exact topology declarations with policy-bounded envelopes.
Supports dynamic step counts and conditional branching while preserving
pre-execution authorization of permitted execution structures.
"""

import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Set, Optional, List


class StepType(str, Enum):
    RAG        = "rag"
    TOOL       = "tool"
    LLM        = "llm"
    BRANCH     = "branch"
    SUBAGENT   = "subagent"
    VALIDATION = "validation"
    SYNTHESIS  = "synthesis"


class DeviationCode(str, Enum):
    ENVELOPE_COUNT_VIOLATION = "ENVELOPE_COUNT_VIOLATION"
    ENVELOPE_TYPE_VIOLATION  = "ENVELOPE_TYPE_VIOLATION"
    ENVELOPE_DEPTH_VIOLATION = "ENVELOPE_DEPTH_VIOLATION"
    INVALID_BRANCH_ID        = "INVALID_BRANCH_ID"
    NONCE_INVALID            = "NONCE_INVALID"
    REPLAY_DETECTED          = "REPLAY_DETECTED"
    SUBAGENT_LEAF_MISMATCH   = "SUBAGENT_LEAF_MISMATCH"


@dataclass(frozen=True)
class SchemaEnvelope:
    """
    Policy-bounded execution envelope for one macro-module.
    Declared and signed before any step executes.
    """
    module_id: str
    min_steps: int
    max_steps: int
    allowed_types: frozenset
    max_depth: int = 1                          # Max subagent recursion depth
    allowed_branches: Optional[frozenset] = None # Pre-committed branch identifiers
    epoch_size: int = 50                        # MMR epoch boundary

    def to_commitment_bytes(self) -> bytes:
        """Deterministic serialization for genesis token signing."""
        d = {
            "module_id": self.module_id,
            "min_steps": self.min_steps,
            "max_steps": self.max_steps,
            "allowed_types": sorted(t.value for t in self.allowed_types),
            "max_depth": self.max_depth,
            "allowed_branches": sorted(self.allowed_branches) if self.allowed_branches else None,
            "epoch_size": self.epoch_size,
        }
        return json.dumps(d, sort_keys=True).encode()

    def validate_step_type(self, step_type: StepType) -> Optional[DeviationCode]:
        if step_type not in self.allowed_types:
            return DeviationCode.ENVELOPE_TYPE_VIOLATION
        return None

    def validate_branch(self, branch_id: str) -> Optional[DeviationCode]:
        if self.allowed_branches is not None and branch_id not in self.allowed_branches:
            return DeviationCode.INVALID_BRANCH_ID
        return None

    def validate_at_closure(self, observed_count: int, observed_depth: int) -> List[DeviationCode]:
        violations = []
        if not (self.min_steps <= observed_count <= self.max_steps):
            violations.append(DeviationCode.ENVELOPE_COUNT_VIOLATION)
        if observed_depth > self.max_depth:
            violations.append(DeviationCode.ENVELOPE_DEPTH_VIOLATION)
        return violations


@dataclass
class GenesisCommitment:
    """
    Signed genesis token anchoring the entire execution session.
    Contains pre-committed envelopes for all declared modules.
    """
    session_id: str
    query_hash: bytes
    monotonic_counter: int
    envelope_hashes: dict  # module_id -> sha256(envelope bytes)
    enclave_sig: bytes     # TEE signature over this commitment

    def to_bytes(self) -> bytes:
        d = {
            "session_id": self.session_id,
            "query_hash": self.query_hash.hex(),
            "counter": self.monotonic_counter,
            "envelopes": {k: v.hex() for k, v in self.envelope_hashes.items()},
        }
        return json.dumps(d, sort_keys=True).encode()

    def commitment_hash(self) -> bytes:
        return hashlib.sha3_256(self.to_bytes()).digest()


def compute_envelope_hash(envelope: SchemaEnvelope) -> bytes:
    return hashlib.sha3_256(envelope.to_commitment_bytes()).digest()
