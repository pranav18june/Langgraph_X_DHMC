import pytest
from dhmc.langgraph_checkpointer import DHMCCheckpointer
from dhmc.schema_envelope import SchemaEnvelope, StepType

def test_checkpointer_initialization():
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=3,
            allowed_types=frozenset([StepType.LLM])
        )
    }
    dhmc = DHMCCheckpointer(session_id="test-session-001", envelopes=envelopes)
    
    assert dhmc.session_id == "test-session-001"
    assert len(dhmc.module_states) == 1
    assert "M1" in dhmc.module_states
    assert dhmc.genesis_commitment is not None
    assert len(dhmc.cas_store) == 0

def test_checkpointer_register_step():
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=3,
            allowed_types=frozenset([StepType.LLM])
        )
    }
    dhmc = DHMCCheckpointer(session_id="test-session-001", envelopes=envelopes)
    
    input_payload = {"input": "test"}
    output_payload = {"output": "result"}
    
    step = dhmc.register_step(
        module_id="M1",
        step_type=StepType.LLM,
        input_payload=input_payload,
        output_payload=output_payload
    )
    
    assert step.module_id == "M1"
    assert step.step_type == StepType.LLM
    assert step.deviation is None
    
    assert len(dhmc.step_records) == 1
    assert len(dhmc.cas_store) == 2  # input and output payloads added to CAS store
    assert dhmc.step_by_id[step.step_id] == step

def test_checkpointer_close_module():
    envelopes = {
        "M1": SchemaEnvelope(
            module_id="M1",
            min_steps=1,
            max_steps=3,
            allowed_types=frozenset([StepType.LLM])
        )
    }
    dhmc = DHMCCheckpointer(session_id="test-session-001", envelopes=envelopes)
    
    dhmc.register_step(
        module_id="M1",
        step_type=StepType.LLM,
        input_payload={"input": "test"},
        output_payload={"output": "result"}
    )
    
    module_hash = dhmc.close_module("M1")
    assert module_hash is not None
    assert len(module_hash) == 32
    assert dhmc.module_states["M1"].is_closed is True
    assert len(dhmc.module_chain) == 1
