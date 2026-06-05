import pytest
from dhmc.langgraph_checkpointer import DHMCCheckpointer, DHMCModuleState
from dhmc.schema_envelope import SchemaEnvelope, StepType
from dhmc.auditor import DHMCAuditor
from dhmc.mmr_engine import MerkleMountainRange


def _make_parent_checkpointer():
    """Helper: create a parent DHMCCheckpointer with one module for sub-agent testing."""
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=10,
            allowed_types=frozenset([StepType.LLM, StepType.SUBAGENT]),
        ),
    }
    return DHMCCheckpointer(session_id="parent-session", envelopes=envelopes)


def test_spawn_subagent_creates_valid_child():
    """A spawned child DHMC should have all required attributes initialized."""
    parent = _make_parent_checkpointer()
    step = parent.register_step("M1", StepType.LLM, {"q": "hello"}, {"a": "world"})

    child = parent.spawn_subagent_dhmc(
        parent_module_id="M1",
        parent_step_id=step.step_id,
    )

    # Required attributes
    assert hasattr(child, "session_id"), "Child should have session_id"
    assert hasattr(child, "cas_store"), "Child should have cas_store"
    assert hasattr(child, "step_records"), "Child should have step_records"
    assert hasattr(child, "module_states"), "Child should have module_states"
    assert hasattr(child, "module_chain"), "Child should have module_chain"
    assert hasattr(child, "enclave"), "Child should have enclave"
    assert hasattr(child, "_prev_module_hash"), "Child should have _prev_module_hash"

    # Session ID should reference parent
    assert "parent-session" in child.session_id, (
        f"Child session_id should reference parent, got {child.session_id}"
    )
    assert "sub" in child.session_id, (
        f"Child session_id should contain 'sub', got {child.session_id}"
    )

    # Child should start empty
    assert len(child.step_records) == 0, "Child should start with no step records"
    assert len(child.module_chain) == 0, "Child should start with no module chain"


def test_subagent_genesis_bound_to_parent():
    """The child's genesis hash should be derived from the parent's chain state."""
    parent = _make_parent_checkpointer()
    step = parent.register_step("M1", StepType.LLM, {"q": "test"}, {"a": "ok"})

    parent_chain_state = parent._prev_module_hash

    child = parent.spawn_subagent_dhmc(
        parent_module_id="M1",
        parent_step_id=step.step_id,
    )

    # Child genesis should not be all zeros (it's derived from parent state)
    assert child._prev_module_hash != b"\x00" * 32, (
        "Child genesis hash should not be all-zero — it should be bound to parent"
    )
    # Child genesis should be 32 bytes (BLAKE3 output)
    assert len(child._prev_module_hash) == 32, (
        f"Child genesis hash should be 32 bytes, got {len(child._prev_module_hash)}"
    )


def test_spawn_different_steps_produce_different_genesis():
    """Spawning from different parent steps should produce different child genesis hashes."""
    parent = _make_parent_checkpointer()
    step1 = parent.register_step("M1", StepType.LLM, {"q": "first"}, {"a": "1"})
    step2 = parent.register_step("M1", StepType.LLM, {"q": "second"}, {"a": "2"})

    child1 = parent.spawn_subagent_dhmc("M1", step1.step_id)
    child2 = parent.spawn_subagent_dhmc("M1", step2.step_id)

    # Each spawn uses fresh TRNG, so genesis hashes should differ
    assert child1._prev_module_hash != child2._prev_module_hash, (
        "Children spawned from different steps should have different genesis hashes"
    )


def test_collapse_subagent_creates_leaf():
    """Collapsing a child DHMC into the parent should create a step record in the parent."""
    parent = _make_parent_checkpointer()
    step = parent.register_step("M1", StepType.LLM, {"q": "setup"}, {"a": "ready"})

    child = parent.spawn_subagent_dhmc("M1", step.step_id)

    # Give the child some envelopes and register steps
    child_envelope = SchemaEnvelope(
        module_id="C1",
        min_steps=1,
        max_steps=3,
        allowed_types=frozenset([StepType.LLM]),
    )
    child.envelopes = {"C1": child_envelope}
    child.module_states["C1"] = DHMCModuleState("C1", child_envelope, MerkleMountainRange(epoch_size=child_envelope.epoch_size))
    child.steps_by_module = {"C1": []}
    child.module_close_order = ["C1"]

    child.register_step("C1", StepType.LLM, {"sub_q": "child input"}, {"sub_a": "child output"})
    child.close_module("C1")

    parent_steps_before = len(parent.step_records)

    # Collapse child into parent
    collapse_record = parent.collapse_subagent(
        parent_module_id="M1",
        step_type=StepType.SUBAGENT,
        child_dhmc=child,
        input_payload={"child_session": child.session_id},
    )

    assert len(parent.step_records) == parent_steps_before + 1, (
        "Collapsing a subagent should add one step record to the parent"
    )
    assert collapse_record.module_id == "M1", (
        "Collapse record should belong to the parent module"
    )
    assert collapse_record.step_type == StepType.SUBAGENT, (
        "Collapse record should have SUBAGENT step type"
    )
    # The output payload should reference the child session
    output_payload = parent.get_payload(collapse_record.output_cas_uri)
    assert output_payload is not None, "Collapse output payload should be in CAS"
    assert "subagent_session" in output_payload, (
        "Collapse output should contain subagent_session"
    )
    assert "final_hash" in output_payload, (
        "Collapse output should contain final_hash"
    )


def test_collapse_subagent_binding_integrity():
    """A parent session with collapsed subagent should pass a full audit as CLEAN."""
    parent = _make_parent_checkpointer()
    step = parent.register_step("M1", StepType.LLM, {"q": "init"}, {"a": "ok"})

    child = parent.spawn_subagent_dhmc("M1", step.step_id)

    # Set up child with envelopes and module state
    child_envelope = SchemaEnvelope(
        module_id="C1",
        min_steps=1,
        max_steps=3,
        allowed_types=frozenset([StepType.LLM]),
    )
    child.envelopes = {"C1": child_envelope}
    child.module_states["C1"] = DHMCModuleState("C1", child_envelope, MerkleMountainRange(epoch_size=child_envelope.epoch_size))
    child.steps_by_module = {"C1": []}
    child.module_close_order = ["C1"]

    child.register_step("C1", StepType.LLM, {"cq": "sub-question"}, {"ca": "sub-answer"})
    child.close_module("C1")

    # Collapse into parent
    parent.collapse_subagent(
        parent_module_id="M1",
        step_type=StepType.SUBAGENT,
        child_dhmc=child,
        input_payload={"child_session": child.session_id},
    )
    parent.close_module("M1")

    # Audit the parent — should be CLEAN
    auditor = DHMCAuditor()
    report = auditor.audit(parent)

    assert report.verdict == "CLEAN", (
        f"Parent with collapsed subagent should audit CLEAN, got {report.verdict}. "
        f"Failed findings: {[(f.check, f.detail) for f in report.findings if not f.passed]}"
    )


def test_subagent_export_and_audit():
    """Verify that a sub-agent checkpointer (which has genesis_commitment = None) can be exported and audited without crashes."""
    parent = _make_parent_checkpointer()
    step = parent.register_step("M1", StepType.LLM, {"q": "init"}, {"a": "ok"})

    child = parent.spawn_subagent_dhmc("M1", step.step_id)

    child_envelope = SchemaEnvelope(
        module_id="C1",
        min_steps=1,
        max_steps=3,
        allowed_types=frozenset([StepType.LLM]),
    )
    child.envelopes = {"C1": child_envelope}
    child.module_states["C1"] = DHMCModuleState("C1", child_envelope, MerkleMountainRange(epoch_size=child_envelope.epoch_size))
    child.steps_by_module = {"C1": []}
    child.module_close_order = ["C1"]

    child.register_step("C1", StepType.LLM, {"cq": "sub-question"}, {"ca": "sub-answer"})
    child.close_module("C1")

    # 1. Verify export_chain does not crash and returns genesis_commitment = None
    exported = child.export_chain()
    assert exported["genesis_commitment"] is None, (
        "Sub-agent chain should have genesis_commitment = None"
    )

    # 2. Verify auditing the child directly does not crash and yields CLEAN
    auditor = DHMCAuditor()
    report = auditor.audit(child)
    assert report.verdict == "CLEAN", (
        f"Sub-agent audit should return CLEAN, got {report.verdict}"
    )

