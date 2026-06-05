import pytest
from dhmc.langgraph_checkpointer import DHMCCheckpointer
from dhmc.schema_envelope import SchemaEnvelope, StepType, DeviationCode
from dhmc.auditor import DHMCAuditor, ForensicReport


def _make_three_module_checkpointer():
    """Helper: create a DHMCCheckpointer with three modules (M1, M2, M3)."""
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=3,
            allowed_types=frozenset([StepType.LLM]),
        ),
        "M2": SchemaEnvelope(
            module_id="M2",
            min_steps=1,
            max_steps=5,
            allowed_types=frozenset([StepType.RAG, StepType.TOOL, StepType.VALIDATION]),
            allowed_branches=frozenset(["fraud_check", "standard"]),
        ),
        "M3": SchemaEnvelope(
            module_id="M3",
            min_steps=1,
            max_steps=2,
            allowed_types=frozenset([StepType.LLM, StepType.SYNTHESIS]),
        ),
    }
    return DHMCCheckpointer(session_id="audit-test-session", envelopes=envelopes)


def _build_clean_session(dhmc):
    """Register steps in M1, M2, M3 and close each module. Returns the dhmc."""
    # M1: two LLM steps
    dhmc.register_step("M1", StepType.LLM, {"q": "hello"}, {"a": "world"})
    dhmc.register_step("M1", StepType.LLM, {"q": "follow-up"}, {"a": "response"})
    dhmc.close_module("M1")

    # M2: three steps with allowed types
    dhmc.register_step("M2", StepType.RAG, {"doc": "ref1"}, {"chunks": ["c1"]})
    dhmc.register_step("M2", StepType.TOOL, {"tool": "calc"}, {"result": 42})
    dhmc.register_step("M2", StepType.VALIDATION, {"check": True}, {"valid": True})
    dhmc.close_module("M2")

    # M3: one synthesis step
    dhmc.register_step("M3", StepType.SYNTHESIS, {"parts": [1, 2]}, {"final": "done"})
    dhmc.close_module("M3")

    return dhmc


def test_audit_clean_session():
    """A fully clean session with three modules should produce CLEAN verdict."""
    dhmc = _make_three_module_checkpointer()
    _build_clean_session(dhmc)

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "CLEAN", (
        f"Expected CLEAN verdict for untampered session, got {report.verdict}"
    )
    assert report.breach_localized_to is None, (
        "No breach should be localized in a clean session"
    )
    # All findings should pass
    for finding in report.findings:
        assert finding.passed is True, (
            f"Finding '{finding.check}' unexpectedly failed: {finding.detail}"
        )


def test_audit_detects_cas_tamper():
    """Tampering with a CAS entry should produce TAMPERED verdict and identify the step."""
    dhmc = _make_three_module_checkpointer()
    _build_clean_session(dhmc)

    # Pick the first step's input CAS URI and tamper with it
    target_step = dhmc.step_records[0]
    target_uri = target_step.input_cas_uri
    dhmc.cas_store[target_uri] = {"TAMPERED": "evil payload"}

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "TAMPERED", (
        f"Expected TAMPERED verdict after CAS modification, got {report.verdict}"
    )
    # The breach should be localized to the tampered step
    assert report.breach_localized_to == target_step.step_id, (
        f"Expected breach at step {target_step.step_id}, "
        f"got {report.breach_localized_to}"
    )
    # At least one finding should fail on leaf hash recomputation
    failed_checks = [f for f in report.findings if not f.passed]
    assert len(failed_checks) > 0, "Should have at least one failed finding"
    leaf_hash_failures = [
        f for f in failed_checks if "Leaf hash recomputation" in f.check
    ]
    assert len(leaf_hash_failures) > 0, (
        "CAS tampering should trigger a leaf hash recomputation failure"
    )


def test_audit_detects_nonce_collision():
    """Two steps sharing the same nonce should produce TAMPERED verdict."""
    dhmc = _make_three_module_checkpointer()

    step1 = dhmc.register_step("M1", StepType.LLM, {"a": 1}, {"b": 2})
    step2 = dhmc.register_step("M1", StepType.LLM, {"c": 3}, {"d": 4})
    dhmc.close_module("M1")

    # Force a nonce collision by copying step1's nonce onto step2
    step2.nonce = step1.nonce

    # Close remaining modules with minimal valid steps
    dhmc.register_step("M2", StepType.RAG, {"x": 1}, {"y": 2})
    dhmc.close_module("M2")
    dhmc.register_step("M3", StepType.LLM, {"p": 1}, {"q": 2})
    dhmc.close_module("M3")

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "TAMPERED", (
        f"Expected TAMPERED verdict for nonce collision, got {report.verdict}"
    )
    nonce_failures = [
        f for f in report.findings
        if f.check == "Nonce uniqueness" and not f.passed
    ]
    assert len(nonce_failures) > 0, (
        "Should have a nonce uniqueness failure finding"
    )
    assert nonce_failures[0].step_id == step2.step_id, (
        "Nonce collision should be attributed to the second step with the duplicate"
    )


def test_audit_detects_monotonic_counter_regression():
    """Steps with a backwards-moving monotonic counter should produce TAMPERED verdict."""
    dhmc = _make_three_module_checkpointer()

    step1 = dhmc.register_step("M1", StepType.LLM, {"a": 1}, {"b": 2})
    step2 = dhmc.register_step("M1", StepType.LLM, {"c": 3}, {"d": 4})
    dhmc.close_module("M1")

    # Force counter regression: make step2's counter lower than step1's
    step2.monotonic_counter = step1.monotonic_counter - 1

    # Close remaining modules
    dhmc.register_step("M2", StepType.RAG, {"x": 1}, {"y": 2})
    dhmc.close_module("M2")
    dhmc.register_step("M3", StepType.LLM, {"p": 1}, {"q": 2})
    dhmc.close_module("M3")

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "TAMPERED", (
        f"Expected TAMPERED for counter regression, got {report.verdict}"
    )
    counter_findings = [
        f for f in report.findings if f.check == "Monotonic counter ordering"
    ]
    assert len(counter_findings) == 1, "Should have exactly one counter ordering finding"
    assert counter_findings[0].passed is False, (
        "Monotonic counter ordering check should fail on counter regression"
    )


def test_audit_detects_schema_violation():
    """Exceeding max_steps should produce POLICY_VIOLATION verdict at audit time."""
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=2,  # Only allow 2 steps
            allowed_types=frozenset([StepType.LLM]),
        ),
    }
    dhmc = DHMCCheckpointer(session_id="schema-violation-test", envelopes=envelopes)

    # Register 3 steps — exceeds max_steps of 2
    dhmc.register_step("M1", StepType.LLM, {"a": 1}, {"b": 2})
    dhmc.register_step("M1", StepType.LLM, {"c": 3}, {"d": 4})
    dhmc.register_step("M1", StepType.LLM, {"e": 5}, {"f": 6})
    dhmc.close_module("M1")

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "POLICY_VIOLATION", (
        f"Expected POLICY_VIOLATION for exceeding max_steps, got {report.verdict}"
    )
    schema_failures = [
        f for f in report.findings
        if "Schema envelope conformance" in f.check and not f.passed
    ]
    assert len(schema_failures) > 0, (
        "Should have a schema envelope conformance failure"
    )
    assert "ENVELOPE_COUNT_VIOLATION" in schema_failures[0].detail, (
        "Violation detail should mention ENVELOPE_COUNT_VIOLATION"
    )


def test_audit_detects_deviation_record():
    """A step with a disallowed step type should create a deviation record flagged by audit."""
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=5,
            allowed_types=frozenset([StepType.LLM]),  # Only LLM allowed
        ),
    }
    dhmc = DHMCCheckpointer(session_id="deviation-test", envelopes=envelopes)

    # Register a step with a disallowed type (TOOL not in allowed_types)
    step = dhmc.register_step("M1", StepType.TOOL, {"tool": "calc"}, {"r": 42})
    assert step.deviation == DeviationCode.ENVELOPE_TYPE_VIOLATION, (
        "Step with disallowed type should carry a deviation code"
    )

    dhmc.close_module("M1")

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.verdict == "POLICY_VIOLATION", (
        f"Expected POLICY_VIOLATION for deviation record, got {report.verdict}"
    )
    deviation_findings = [
        f for f in report.findings
        if f.check == "Deviation record review" and not f.passed
    ]
    assert len(deviation_findings) > 0, (
        "Audit should have a failing deviation record review finding"
    )
    assert deviation_findings[0].step_id == step.step_id, (
        "Deviation finding should reference the step with the disallowed type"
    )
    assert deviation_findings[0].forensic_evidence is not None, (
        "Deviation finding should include forensic evidence"
    )
    assert deviation_findings[0].forensic_evidence["deviation_code"] == "ENVELOPE_TYPE_VIOLATION", (
        "Forensic evidence should carry the ENVELOPE_TYPE_VIOLATION code"
    )


def test_forensic_drill_down_returns_evidence():
    """forensic_drill_down should return structured evidence for a given step."""
    dhmc = _make_three_module_checkpointer()
    _build_clean_session(dhmc)

    # Tamper with CAS to create a breach
    target_step = dhmc.step_records[0]
    target_uri = target_step.input_cas_uri
    dhmc.cas_store[target_uri] = {"TAMPERED": "payload"}

    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)

    assert report.breach_localized_to is not None, (
        "Should have a breach step after CAS tampering"
    )

    evidence = auditor.forensic_drill_down(dhmc, report.breach_localized_to)

    assert "error" not in evidence, (
        f"Drill-down should not error for a valid step, got: {evidence}"
    )
    assert "forensic_finding" in evidence, "Evidence should contain forensic_finding"
    assert "chain_of_custody" in evidence, "Evidence should contain chain_of_custody"
    assert "payload_evidence" in evidence, "Evidence should contain payload_evidence"

    finding = evidence["forensic_finding"]
    assert finding["step_id"] == target_step.step_id, (
        "Forensic finding step_id should match the breach step"
    )
    assert finding["module_id"] == target_step.module_id, (
        "Forensic finding module_id should match"
    )
    assert finding["step_type"] == target_step.step_type.value, (
        "Forensic finding step_type should match"
    )
    assert finding["timestamp"] is not None, "Timestamp should be present"

    custody = evidence["chain_of_custody"]
    assert "pre_hash" in custody, "Chain of custody should include pre_hash"
    assert "post_hash" in custody, "Chain of custody should include post_hash"
    assert "binding" in custody, "Chain of custody should include binding"
    assert "nonce" in custody, "Chain of custody should include nonce"
    assert "monotonic_counter" in custody, "Chain of custody should include monotonic_counter"

    payload_ev = evidence["payload_evidence"]
    assert "input_cas_uri" in payload_ev, "Payload evidence should include input_cas_uri"
    assert "output_cas_uri" in payload_ev, "Payload evidence should include output_cas_uri"
    assert "input_payload" in payload_ev, "Payload evidence should include input_payload"
    assert "output_payload" in payload_ev, "Payload evidence should include output_payload"


def test_verdict_escalation_no_downgrade():
    """Verify that a TAMPERED verdict cannot be downgraded to POLICY_VIOLATION by subsequent steps."""
    # Build a checkpointer
    dhmc = _make_three_module_checkpointer()
    
    # 1. Step 1: Normal LLM step in M1
    dhmc.register_step("M1", StepType.LLM, {"q": "1"}, {"a": "1"})
    dhmc.close_module("M1")
    
    # 2. Step 2: RAG step in M2 (normal)
    step2 = dhmc.register_step("M2", StepType.RAG, {"q": "2"}, {"a": "2"})
    
    # 3. Step 3: Trigger POLICY_VIOLATION (deviation) on M2 by registering SYNTHESIS
    step3 = dhmc.register_step("M2", StepType.SYNTHESIS, {"q": "3"}, {"a": "3"})
    assert step3.deviation == DeviationCode.ENVELOPE_TYPE_VIOLATION
    
    # 4. Close M2
    dhmc.close_module("M2")
    
    # 5. M3: one synthesis step (normal)
    dhmc.register_step("M3", StepType.SYNTHESIS, {"parts": [1]}, {"final": "ok"})
    dhmc.close_module("M3")
    
    # Force a nonce collision between step2 and step3 to trigger TAMPERED
    step3.nonce = step2.nonce
    
    # Verify that the auditor audit returns TAMPERED
    auditor = DHMCAuditor()
    report = auditor.audit(dhmc)
    
    assert report.verdict == "TAMPERED", (
        f"Expected TAMPERED verdict, got {report.verdict} (might have been downgraded to POLICY_VIOLATION)"
    )

