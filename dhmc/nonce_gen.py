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


def _blake3(*parts: bytes) -> bytes:
    h = hashlib.sha3_256()
    for p in parts:
        h.update(p)
    return h.digest()


@dataclass
class RegistrationToken:
    step_id: str
    nonce: bytes
    module_hash_bound: bytes   # H(M_{t-1}) at time of issuance
    monotonic_counter: int
    issued_at: float
    enclave_sig: bytes         # HMAC with session key (simulates TEE attestation)


class SimulatedTEEEnclave:
    """
    Simulates a Trusted Execution Environment enclave.
    
    Boundary properties modeled:
    - Session key inaccessible to orchestrator (held only in this object)
    - TRNG output unpredictable to orchestrator  
    - Monotonic counter non-resettable by orchestrator
    
    Production replacement: Unix socket to actual enclave process.
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
