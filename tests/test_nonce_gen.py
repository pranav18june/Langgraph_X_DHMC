import pytest
from dhmc.nonce_gen import SimulatedTEEEnclave, RegistrationToken


def test_enclave_produces_unique_nonces():
    """100 registration tokens should all have unique nonces."""
    enclave = SimulatedTEEEnclave(session_id="nonce-test")
    nonces = set()
    for i in range(100):
        token = enclave.issue_registration_token(f"step-{i:04d}")
        nonces.add(token.nonce)

    assert len(nonces) == 100, (
        f"Expected 100 unique nonces, got {len(nonces)} — nonce collision detected"
    )


def test_enclave_monotonic_counter_increases():
    """Each token's monotonic counter should be strictly one greater than the previous."""
    enclave = SimulatedTEEEnclave(session_id="counter-test")
    prev_counter = enclave.current_counter

    for i in range(20):
        token = enclave.issue_registration_token(f"step-{i}")
        assert token.monotonic_counter == prev_counter + 1, (
            f"Token {i}: expected counter {prev_counter + 1}, "
            f"got {token.monotonic_counter}"
        )
        prev_counter = token.monotonic_counter


def test_enclave_verify_token_valid():
    """A genuinely issued token should pass verification."""
    enclave = SimulatedTEEEnclave(session_id="verify-test")
    token = enclave.issue_registration_token("step-0001")

    assert enclave.verify_token(token) is True, (
        "A token issued by the enclave should pass verification"
    )


def test_enclave_verify_token_tampered():
    """Modifying the nonce of a token should cause verification to fail."""
    enclave = SimulatedTEEEnclave(session_id="tamper-verify-test")
    token = enclave.issue_registration_token("step-0001")

    # Tamper with the nonce by flipping all bits
    original_nonce = token.nonce
    tampered_nonce = bytes(b ^ 0xFF for b in original_nonce)
    token.nonce = tampered_nonce

    assert enclave.verify_token(token) is False, (
        "A token with a tampered nonce should fail verification"
    )


def test_enclave_verify_token_counter_tampered():
    """Modifying the monotonic counter should cause verification to fail."""
    enclave = SimulatedTEEEnclave(session_id="counter-tamper-test")
    token = enclave.issue_registration_token("step-0001")

    token.monotonic_counter += 100

    assert enclave.verify_token(token) is False, (
        "A token with a tampered monotonic counter should fail verification"
    )


def test_enclave_advance_module_updates_state():
    """After advancing module hash, new tokens should be bound to the new hash."""
    enclave = SimulatedTEEEnclave(session_id="advance-test")

    new_module_hash = b"\xab" * 32
    enclave.advance_module(new_module_hash)

    token = enclave.issue_registration_token("step-after-advance")

    assert token.module_hash_bound == new_module_hash, (
        f"Token should be bound to the advanced module hash, "
        f"got {token.module_hash_bound.hex()[:16]}"
    )


def test_enclave_advance_module_changes_nonce_derivation():
    """Tokens issued before and after advance_module should use different chain bindings."""
    enclave = SimulatedTEEEnclave(session_id="advance-derivation-test")

    token_before = enclave.issue_registration_token("step-before")
    hash_bound_before = token_before.module_hash_bound

    enclave.advance_module(b"\xff" * 32)
    token_after = enclave.issue_registration_token("step-after")
    hash_bound_after = token_after.module_hash_bound

    assert hash_bound_before != hash_bound_after, (
        "Module hash binding should change after advance_module"
    )


def test_spawn_nonce_is_unique():
    """Multiple spawn nonces should all be unique."""
    enclave = SimulatedTEEEnclave(session_id="spawn-test")
    parent_hash = b"\x01" * 32

    spawn_nonces = set()
    for i in range(50):
        nonce = enclave.issue_spawn_nonce(f"parent-step-{i}", parent_hash)
        spawn_nonces.add(nonce)

    assert len(spawn_nonces) == 50, (
        f"Expected 50 unique spawn nonces, got {len(spawn_nonces)}"
    )


def test_spawn_nonce_is_32_bytes():
    """Each spawn nonce should be exactly 32 bytes."""
    enclave = SimulatedTEEEnclave(session_id="spawn-size-test")
    nonce = enclave.issue_spawn_nonce("parent-step", b"\x00" * 32)

    assert len(nonce) == 32, (
        f"Spawn nonce should be 32 bytes, got {len(nonce)}"
    )


def test_enclave_initial_state():
    """A freshly created enclave should have counter 0 and zero-byte module hash."""
    enclave = SimulatedTEEEnclave(session_id="init-test")

    assert enclave.current_counter == 0, (
        f"Initial counter should be 0, got {enclave.current_counter}"
    )
    assert enclave.current_module_hash == b"\x00" * 32, (
        "Initial module hash should be 32 zero bytes"
    )


def test_enclave_genesis_commitment():
    """issue_genesis_commitment should return a valid GenesisCommitment and increment counter."""
    enclave = SimulatedTEEEnclave(session_id="genesis-test")
    initial_counter = enclave.current_counter

    gc = enclave.issue_genesis_commitment(
        query_hash=b"\x00" * 32,
        envelope_hashes={"M1": b"\xab" * 32},
    )

    assert gc.session_id == "genesis-test", "Genesis commitment should carry session_id"
    assert gc.query_hash == b"\x00" * 32, "Genesis commitment should carry query_hash"
    assert gc.monotonic_counter == initial_counter + 1, (
        "Genesis commitment should increment monotonic counter"
    )
    assert gc.enclave_sig is not None, "Genesis commitment should have an enclave signature"
    assert len(gc.enclave_sig) == 32, "Enclave signature should be 32 bytes (SHA-256 HMAC)"
