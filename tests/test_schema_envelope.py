import pytest
from dhmc.schema_envelope import (
    SchemaEnvelope,
    StepType,
    DeviationCode,
    GenesisCommitment,
    compute_envelope_hash,
)


def test_envelope_allows_valid_step_type():
    """A step type within allowed_types should produce no deviation."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM, StepType.TOOL]),
    )
    result = envelope.validate_step_type(StepType.LLM)
    assert result is None, (
        f"Valid step type LLM should produce no deviation, got {result}"
    )
    result = envelope.validate_step_type(StepType.TOOL)
    assert result is None, (
        f"Valid step type TOOL should produce no deviation, got {result}"
    )


def test_envelope_rejects_invalid_step_type():
    """A step type outside allowed_types should produce ENVELOPE_TYPE_VIOLATION."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
    )
    result = envelope.validate_step_type(StepType.RAG)
    assert result == DeviationCode.ENVELOPE_TYPE_VIOLATION, (
        f"Disallowed step type RAG should produce ENVELOPE_TYPE_VIOLATION, got {result}"
    )


def test_envelope_allows_valid_branch():
    """A branch within allowed_branches should produce no deviation."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
        allowed_branches=frozenset(["standard", "fraud_check"]),
    )
    result = envelope.validate_branch("standard")
    assert result is None, (
        f"Valid branch 'standard' should produce no deviation, got {result}"
    )
    result = envelope.validate_branch("fraud_check")
    assert result is None, (
        f"Valid branch 'fraud_check' should produce no deviation, got {result}"
    )


def test_envelope_rejects_invalid_branch():
    """A branch outside allowed_branches should produce INVALID_BRANCH_ID."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
        allowed_branches=frozenset(["standard"]),
    )
    result = envelope.validate_branch("rogue_branch")
    assert result == DeviationCode.INVALID_BRANCH_ID, (
        f"Disallowed branch should produce INVALID_BRANCH_ID, got {result}"
    )


def test_envelope_branch_none_allows_any():
    """When allowed_branches is None, any branch should be accepted."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
        allowed_branches=None,
    )
    result = envelope.validate_branch("any_branch_name")
    assert result is None, (
        "With allowed_branches=None, any branch should be accepted"
    )


def test_envelope_closure_within_bounds():
    """Closure with count in [min, max] and depth <= max_depth should produce no violations."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=2,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
        max_depth=3,
    )
    # Exactly at min
    violations = envelope.validate_at_closure(observed_count=2, observed_depth=0)
    assert violations == [], (
        f"Count at min_steps should produce no violations, got {violations}"
    )
    # In the middle
    violations = envelope.validate_at_closure(observed_count=3, observed_depth=1)
    assert violations == [], (
        f"Count within bounds should produce no violations, got {violations}"
    )
    # Exactly at max
    violations = envelope.validate_at_closure(observed_count=5, observed_depth=3)
    assert violations == [], (
        f"Count at max_steps and depth at max_depth should produce no violations, got {violations}"
    )


def test_envelope_closure_below_min():
    """Closure with count below min_steps should produce ENVELOPE_COUNT_VIOLATION."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=3,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
    )
    violations = envelope.validate_at_closure(observed_count=2, observed_depth=0)
    assert DeviationCode.ENVELOPE_COUNT_VIOLATION in violations, (
        f"Count below min_steps should trigger ENVELOPE_COUNT_VIOLATION, got {violations}"
    )


def test_envelope_closure_above_max():
    """Closure with count above max_steps should produce ENVELOPE_COUNT_VIOLATION."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=3,
        allowed_types=frozenset([StepType.LLM]),
    )
    violations = envelope.validate_at_closure(observed_count=4, observed_depth=0)
    assert DeviationCode.ENVELOPE_COUNT_VIOLATION in violations, (
        f"Count above max_steps should trigger ENVELOPE_COUNT_VIOLATION, got {violations}"
    )


def test_envelope_closure_depth_violation():
    """Closure with depth > max_depth should produce ENVELOPE_DEPTH_VIOLATION."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM]),
        max_depth=2,
    )
    violations = envelope.validate_at_closure(observed_count=3, observed_depth=3)
    assert DeviationCode.ENVELOPE_DEPTH_VIOLATION in violations, (
        f"Depth exceeding max_depth should trigger ENVELOPE_DEPTH_VIOLATION, got {violations}"
    )


def test_envelope_closure_both_violations():
    """Closure can produce both count and depth violations simultaneously."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=2,
        max_steps=4,
        allowed_types=frozenset([StepType.LLM]),
        max_depth=1,
    )
    violations = envelope.validate_at_closure(observed_count=5, observed_depth=3)
    assert DeviationCode.ENVELOPE_COUNT_VIOLATION in violations, (
        "Should include ENVELOPE_COUNT_VIOLATION"
    )
    assert DeviationCode.ENVELOPE_DEPTH_VIOLATION in violations, (
        "Should include ENVELOPE_DEPTH_VIOLATION"
    )
    assert len(violations) == 2, (
        f"Expected exactly 2 violations, got {len(violations)}"
    )


def test_genesis_commitment_hash_deterministic():
    """Two GenesisCommitments with identical fields should produce the same hash."""
    gc1 = GenesisCommitment(
        session_id="test-session",
        query_hash=b"\x00" * 32,
        monotonic_counter=1,
        envelope_hashes={"M1": b"\xab" * 32},
        enclave_sig=b"\xcd" * 32,
    )
    gc2 = GenesisCommitment(
        session_id="test-session",
        query_hash=b"\x00" * 32,
        monotonic_counter=1,
        envelope_hashes={"M1": b"\xab" * 32},
        enclave_sig=b"\xcd" * 32,
    )
    assert gc1.commitment_hash() == gc2.commitment_hash(), (
        "Identical GenesisCommitments should produce the same commitment hash"
    )
    assert len(gc1.commitment_hash()) == 32, (
        "Commitment hash should be 32 bytes (SHA3-256)"
    )


def test_genesis_commitment_hash_changes_with_input():
    """GenesisCommitments with different fields should produce different hashes."""
    gc1 = GenesisCommitment(
        session_id="session-A",
        query_hash=b"\x00" * 32,
        monotonic_counter=1,
        envelope_hashes={"M1": b"\xab" * 32},
        enclave_sig=b"\xcd" * 32,
    )
    gc2 = GenesisCommitment(
        session_id="session-B",
        query_hash=b"\x00" * 32,
        monotonic_counter=1,
        envelope_hashes={"M1": b"\xab" * 32},
        enclave_sig=b"\xcd" * 32,
    )
    assert gc1.commitment_hash() != gc2.commitment_hash(), (
        "GenesisCommitments with different session_ids should produce different hashes"
    )


def test_compute_envelope_hash_deterministic():
    """compute_envelope_hash should be deterministic for the same envelope."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.LLM, StepType.TOOL]),
    )
    h1 = compute_envelope_hash(envelope)
    h2 = compute_envelope_hash(envelope)
    assert h1 == h2, "Same envelope should produce the same hash"
    assert len(h1) == 32, "Envelope hash should be 32 bytes (SHA3-256)"


def test_to_commitment_bytes_is_deterministic():
    """to_commitment_bytes should produce the same output regardless of frozenset order."""
    envelope = SchemaEnvelope(
        module_id="M1",
        min_steps=1,
        max_steps=5,
        allowed_types=frozenset([StepType.TOOL, StepType.LLM, StepType.RAG]),
    )
    b1 = envelope.to_commitment_bytes()
    b2 = envelope.to_commitment_bytes()
    assert b1 == b2, "to_commitment_bytes should be deterministic"
    # Verify it's valid JSON
    import json
    parsed = json.loads(b1)
    assert parsed["module_id"] == "M1"
    assert parsed["allowed_types"] == sorted(["tool", "llm", "rag"])
