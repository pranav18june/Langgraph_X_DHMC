"""
dhmc/nonce_gen.py
Simulated TEE enclave for nonce generation.
In production: replace with Intel SGX / AMD SEV-SNP / AWS Nitro enclave call.

The enclave holds the session key and issues per-step registration tokens
derived from hardware entropy XOR live chain state. This closes the
nonce-prediction vulnerability in open-topology systems.
"""

import hashlib
import hmac
import os
import json
import time
from dataclasses import dataclass

from .crypto import _blake3


@dataclass
class RegistrationToken:
    step_id: str
    nonce: bytes
    module_hash_bound: bytes   # H(M_{t-1}) at time of issuance
    monotonic_counter: int
    issued_at: float
    enclave_sig: bytes         # HMAC with session key (simulates TEE attestation)


class SoftwareSimulatedEnclave:
    """
    SOFTWARE SIMULATION of a Trusted Execution Environment enclave.
    
    ⚠️ WARNING: This class simulates TEE properties in standard Python.
    All security guarantees (session key isolation, TRNG unpredictability,
    monotonic counter non-resettability) are ILLUSTRATIVE ONLY and do not
    hold against an adversary with access to this Python process.
    
    For production deployment, replace this class with a real TEE interface
    communicating via Unix socket or vsock to a hardware enclave
    (Intel SGX, AMD SEV-SNP, AWS Nitro Enclave).
    
    Boundary properties modeled:
    - Session key inaccessible to orchestrator (held only in this object)
    - TRNG output unpredictable to orchestrator  
    - Monotonic counter non-resettable by orchestrator
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        # Session key: in production, provisioned by remote attestation
        self._session_key = os.urandom(32)
        self._monotonic_counter = 0
        self._prev_module_hash = b'\x00' * 32  # Genesis: all zeros

    def issue_registration_token(self, step_id: str) -> RegistrationToken:
        """
        Core DHMC formula:
        StepNonce_{t,i} = TEE_TRNG() XOR BLAKE3(H(M_{t-1}) || StepID || Counter)
        
        Binds nonce to:
        1. Hardware entropy (unpredictable)  
        2. Live chain state (requires all preceding module hashes)
        3. Monotonic counter (replay resistance)
        """
        self._monotonic_counter += 1

        # Simulated hardware TRNG (in production: SGX rdrand / SEV-SNP TRNG)
        trng_bytes = os.urandom(32)

        # BLAKE3 term: binds to chain state
        chain_binding = _blake3(
            self._prev_module_hash,
            step_id.encode(),
            self._monotonic_counter.to_bytes(8, 'big')
        )

        # XOR combination: nonce is unpredictable AND chain-state-bound
        nonce = bytes(a ^ b for a, b in zip(trng_bytes, chain_binding))

        # Enclave attestation signature (simulated via HMAC with session key)
        sig_payload = json.dumps({
            "step_id": step_id,
            "nonce": nonce.hex(),
            "counter": self._monotonic_counter,
            "module_hash": self._prev_module_hash.hex(),
        }, sort_keys=True).encode()
        sig = hmac.new(self._session_key, sig_payload, hashlib.sha256).digest()

        return RegistrationToken(
            step_id=step_id,
            nonce=nonce,
            module_hash_bound=self._prev_module_hash,
            monotonic_counter=self._monotonic_counter,
            issued_at=time.time(),
            enclave_sig=sig,
        )

    def issue_genesis_commitment(self, query_hash: bytes, envelope_hashes: dict) -> "GenesisCommitment":
        from .schema_envelope import GenesisCommitment
        self._monotonic_counter += 1
        
        d = {
            "session_id": self.session_id,
            "query_hash": query_hash.hex(),
            "counter": self._monotonic_counter,
            "envelopes": {k: v.hex() for k, v in envelope_hashes.items()},
        }
        sig_payload = json.dumps(d, sort_keys=True).encode()
        sig = hmac.new(self._session_key, sig_payload, hashlib.sha256).digest()
        
        return GenesisCommitment(
            session_id=self.session_id,
            query_hash=query_hash,
            monotonic_counter=self._monotonic_counter,
            envelope_hashes=envelope_hashes,
            enclave_sig=sig
        )

    def advance_module(self, new_module_hash: bytes):
        """
        Called at module boundary. Updates the live chain state H(M_{t-1})
        that future nonces will be bound to.
        """
        self._prev_module_hash = new_module_hash

    def verify_token(self, token: RegistrationToken) -> bool:
        """Verify that a registration token was genuinely issued by this enclave."""
        sig_payload = json.dumps({
            "step_id": token.step_id,
            "nonce": token.nonce.hex(),
            "counter": token.monotonic_counter,
            "module_hash": token.module_hash_bound.hex(),
        }, sort_keys=True).encode()
        expected_sig = hmac.new(self._session_key, sig_payload, hashlib.sha256).digest()
        return hmac.compare_digest(token.enclave_sig, expected_sig)

    def issue_spawn_nonce(self, parent_step_id: str, parent_module_hash: bytes) -> bytes:
        """
        For recursive sub-agent spawning: generates a SpawnNonce binding
        the sub-agent's genesis to the parent chain state at spawn time.
        """
        trng_bytes = os.urandom(32)
        chain_binding = _blake3(parent_module_hash, parent_step_id.encode())
        return bytes(a ^ b for a, b in zip(trng_bytes, chain_binding))

    @property
    def current_counter(self) -> int:
        return self._monotonic_counter

    @property
    def current_module_hash(self) -> bytes:
        return self._prev_module_hash


# Backward-compatible alias
SimulatedTEEEnclave = SoftwareSimulatedEnclave
