import sys
import os
import random
from typing import TypedDict, Optional

# Ensure we can import dhmc, dhmc_langgraph_wrapper, and libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../libs/checkpoint")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../libs/langgraph")))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from dhmc_langgraph_wrapper import DHMCWrappedCheckpointer

from dhmc.langgraph_checkpointer import DHMCCheckpointer
from dhmc.schema_envelope import SchemaEnvelope, StepType
from dhmc.auditor import DHMCAuditor
from dhmc.loan_approval import (
    node_intent_parser,
    node_credit_score_retrieval,
    node_income_verification,
    node_ofac_lookup,
    node_fraud_check,
    node_synthesis,
)

# Standard State Definition
class LoanState(TypedDict, total=False):
    query: str
    applicant_name: str
    requested_amount: int
    loan_type: str
    parsed_intent: str
    credit_score: int
    credit_policy: str
    bureau_source: str
    retrieval_doc_hash: str
    monthly_income: int
    employment_status: str
    employer: str
    verification_ref: str
    ofac_status: str
    checked_at: float
    list_version: str
    fraud_risk_score: float
    fraud_signals: list
    recommendation: str
    decision: str
    credit_score_used: int
    threshold_applied: int
    reason: str
    _injected_score: int
    # Output of unauthorized node for Scenario 3
    database_rows_modified: int

# Unauthorized node for Scenario 3
def node_database_write(state: LoanState) -> dict:
    print("  [NODE] Executing unauthorized database_write...")
    return {"database_rows_modified": 47}

# Shared parent wrapper reference for Scenario 4 sub-agent execution
shared_parent_wrapper = None

def node_bureau_lookup_agent(state: LoanState) -> dict:
    print("  [NODE] Spawning sub-agent for bureau lookup...")
    parent_step_id = "M2:step:0001:credit-retrieval"
    
    # Spawn child checkpointer using the core DHMC spawn method
    child_dhmc = shared_parent_wrapper.dhmc.spawn_subagent_dhmc(
        parent_module_id="M2",
        parent_step_id=parent_step_id
    )
    
    # Configure envelopes for sub-agent
    child_dhmc.envelopes["sub_M1"] = SchemaEnvelope("sub_M1", 1, 3, {StepType.RAG, StepType.TOOL})
    # Pre-populate module states
    child_dhmc.module_states["sub_M1"] = __import__(
        'dhmc.langgraph_checkpointer', fromlist=['DHMCModuleState']
    ).DHMCModuleState(
        module_id="sub_M1",
        envelope=child_dhmc.envelopes["sub_M1"],
    )
    
    # Build a real LangGraph sub-graph representing the sub-agent
    sub_builder = StateGraph(LoanState)
    sub_builder.add_node("sub_node", lambda state: {"credit_score": 750, "employment_status": "VERIFIED"})
    sub_builder.add_edge(START, "sub_node")
    sub_builder.add_edge("sub_node", END)
    
    child_wrapper = DHMCWrappedCheckpointer(
        underlying=InMemorySaver(),
        dhmc_instance=child_dhmc,
        node_to_module={"sub_node": "sub_M1"},
        node_to_step_type={"sub_node": StepType.RAG}
    )
    sub_graph = sub_builder.compile(checkpointer=child_wrapper)
    
    # Run the sub-graph
    child_config = {"configurable": {"thread_id": "child-thread"}}
    print("\n[Pregel] Running child sub-graph...")
    sub_graph.invoke(
        {"query": "lookup Bureau Equifax"},
        child_config
    )
    print("[Pregel] Child sub-graph execution finished.")
    
    # Manually close child module since it is not the final parent module
    child_wrapper.dhmc.close_module("sub_M1")
    print(f"[Sub-agent] Child chain final hash: {child_dhmc.enclave.current_module_hash.hex()[:24]}...")
    
    # Register the spawned child checkpointer in-memory in parent checkpointer wrapper for automatic collapse!
    shared_parent_wrapper.register_child_dhmc(child_dhmc)
    
    return {
        "credit_score": 750,
        "employment_status": "VERIFIED",
    }


# Standard routing edge
def route_after_ofac(state: LoanState) -> str:
    # Trigger fraud check on low scores or random risk
    injected = state.get("_injected_score")
    if (injected is not None and injected < 650) or random.random() > 0.4:
        print("  [ROUTER] Risk signal detected or attack simulation active -> Routing to fraud_check")
        return "fraud_check"
    print("  [ROUTER] Direct routing to synthesis")
    return "synthesis"

# Factory for DHMCCheckpointer
def build_dhmc(session_id: str) -> DHMCCheckpointer:
    return DHMCCheckpointer(
        session_id=session_id,
        envelopes={
            "M1": SchemaEnvelope(
                module_id="M1",
                min_steps=1, max_steps=3,
                allowed_types={StepType.LLM},
            ),
            "M2": SchemaEnvelope(
                module_id="M2",
                min_steps=1, max_steps=5,
                allowed_types={StepType.RAG, StepType.TOOL, StepType.VALIDATION, StepType.SUBAGENT},
                allowed_branches={"fraud_check", "standard"},
                epoch_size=10,
            ),
            "M3": SchemaEnvelope(
                module_id="M3",
                min_steps=1, max_steps=2,
                allowed_types={StepType.LLM, StepType.SYNTHESIS},
            ),
        }
    )

# Node module and type mappings
node_to_module = {
    "intent_parser": "M1",
    "credit_retrieval": "M2",
    "income_verification": "M2",
    "ofac_lookup": "M2",
    "fraud_check": "M2",
    "database_write": "M2",  # M2 envelope type violation node
    "synthesis": "M3",
    "bureau_lookup_agent": "M2",
}

node_to_step_type = {
    "intent_parser": StepType.LLM,
    "credit_retrieval": StepType.RAG,
    "income_verification": StepType.TOOL,
    "ofac_lookup": StepType.TOOL,
    "fraud_check": StepType.VALIDATION,
    "database_write": StepType.SYNTHESIS, # Violation: not in M2 allowed_types
    "synthesis": StepType.LLM,
    "bureau_lookup_agent": StepType.SUBAGENT,
}


def scenario_clean():
    print("\n" + "="*60)
    print("SCENARIO 1: Clean Execution (Real LangGraph Graph)")
    print("="*60)
    
    # 1. Setup Graph Builder
    builder = StateGraph(LoanState)
    builder.add_node("intent_parser", node_intent_parser)
    builder.add_node("credit_retrieval", node_credit_score_retrieval)
    builder.add_node("income_verification", node_income_verification)
    builder.add_node("ofac_lookup", node_ofac_lookup)
    builder.add_node("fraud_check", node_fraud_check)
    builder.add_node("synthesis", node_synthesis)
    
    builder.add_edge(START, "intent_parser")
    builder.add_edge("intent_parser", "credit_retrieval")
    builder.add_edge("credit_retrieval", "income_verification")
    builder.add_edge("income_verification", "ofac_lookup")
    builder.add_conditional_edges(
        "ofac_lookup",
        route_after_ofac,
        {"fraud_check": "fraud_check", "synthesis": "synthesis"}
    )
    builder.add_edge("fraud_check", "synthesis")
    builder.add_edge("synthesis", END)
    
    # 2. Wire Checkpointers
    dhmc_instance = build_dhmc("loan-clean-001")
    # Since Scenario 1 has 4 steps in M2, set min_steps=3
    dhmc_instance.envelopes["M2"].min_steps = 3
    
    memory = InMemorySaver()
    wrapped_checkpointer = DHMCWrappedCheckpointer(
        underlying=memory,
        dhmc_instance=dhmc_instance,
        node_to_module=node_to_module,
        node_to_step_type=node_to_step_type,
    )
    
    graph = builder.compile(checkpointer=wrapped_checkpointer)
    
    # 3. Run Pipeline
    config = {"configurable": {"thread_id": "loan-clean-thread"}}
    initial_state = {
        "query": "I need a personal loan of $50,000 for home renovation.",
        "applicant_name": "Rahul Sharma",
        "requested_amount": 50000,
        "loan_type": "personal",
    }
    
    print("\n[Pregel] Starting real LangGraph loop...")
    result = graph.invoke(initial_state, config)
    print("[Pregel] LangGraph loop finished.")
    
    # 4. Audit
    auditor = DHMCAuditor()
    report = auditor.audit(dhmc_instance)
    report.print_report()


def scenario_context_hijack():
    print("\n" + "="*60)
    print("SCENARIO 2: Context Hijack — Post-Execution CAS Tampering")
    print("Attacker modifies credit document in CAS after clean execution")
    print("="*60)
    
    # Setup graph
    builder = StateGraph(LoanState)
    builder.add_node("intent_parser", node_intent_parser)
    builder.add_node("credit_retrieval", node_credit_score_retrieval)
    builder.add_node("income_verification", node_income_verification)
    builder.add_node("ofac_lookup", node_ofac_lookup)
    builder.add_node("fraud_check", node_fraud_check)
    builder.add_node("synthesis", node_synthesis)
    
    builder.add_edge(START, "intent_parser")
    builder.add_edge("intent_parser", "credit_retrieval")
    builder.add_edge("credit_retrieval", "income_verification")
    builder.add_edge("income_verification", "ofac_lookup")
    builder.add_conditional_edges(
        "ofac_lookup",
        route_after_ofac,
        {"fraud_check": "fraud_check", "synthesis": "synthesis"}
    )
    builder.add_edge("fraud_check", "synthesis")
    builder.add_edge("synthesis", END)
    
    dhmc_instance = build_dhmc("loan-attack-hijack-001")
    dhmc_instance.envelopes["M2"].min_steps = 3
    
    memory = InMemorySaver()
    wrapped_checkpointer = DHMCWrappedCheckpointer(
        underlying=memory,
        dhmc_instance=dhmc_instance,
        node_to_module=node_to_module,
        node_to_step_type=node_to_step_type,
    )
    
    graph = builder.compile(checkpointer=wrapped_checkpointer)
    
    # 1. Legitimate Clean Run
    config = {"configurable": {"thread_id": "loan-hijack-thread"}}
    initial_state = {
        "query": "Loan request.",
        "applicant_name": "Normal Applicant",
        "requested_amount": 50000,
        "loan_type": "personal",
    }
    
    graph.invoke(initial_state, config)
    
    # 2. Tamper CAS Entry
    m2_steps = dhmc_instance.module_states["M2"].steps
    if m2_steps:
        target_step = m2_steps[0]  # Credit score retrieval step
        print(f"\n[ATTACK] Attacker targets M2 step 0 output CAS entry")
        print(f"[ATTACK] URI: {target_step.output_cas_uri}")
        
        # Modify the stored credit policy threshold from 650 -> 100
        dhmc_instance.simulate_post_execution_tamper(
            target_step.output_cas_uri,
            {
                "credit_score": 720,
                "credit_policy": "credit_threshold: 100",  # TAMPERED
                "bureau_source": "Equifax",
                "retrieval_doc_hash": "sha256:abc123authorized",
            }
        )
        
    # 3. Audit
    auditor = DHMCAuditor()
    report = auditor.audit(dhmc_instance)
    report.print_report()
    
    if report.breach_localized_to:
        print(f"\n[DFIR] Breach localized. Drilling down on: {report.breach_localized_to}")
        evidence = auditor.forensic_drill_down(dhmc_instance, report.breach_localized_to)
        import json
        print(json.dumps(evidence, indent=2, default=str))


def scenario_unauthorized_step():
    print("\n" + "="*60)
    print("SCENARIO 3: Unauthorized Step — Schema Envelope Violation")
    print("Graph executes a database_write node (type: SYNTHESIS) mapped to M2")
    print("="*60)
    
    builder = StateGraph(LoanState)
    builder.add_node("intent_parser", node_intent_parser)
    builder.add_node("credit_retrieval", node_credit_score_retrieval)
    builder.add_node("income_verification", node_income_verification)
    builder.add_node("ofac_lookup", node_ofac_lookup)
    builder.add_node("database_write", node_database_write)
    builder.add_node("synthesis", node_synthesis)
    
    builder.add_edge(START, "intent_parser")
    builder.add_edge("intent_parser", "credit_retrieval")
    builder.add_edge("credit_retrieval", "income_verification")
    builder.add_edge("income_verification", "ofac_lookup")
    builder.add_edge("ofac_lookup", "database_write")
    builder.add_edge("database_write", "synthesis")
    builder.add_edge("synthesis", END)
    
    dhmc_instance = build_dhmc("loan-attack-inject-001")
    dhmc_instance.envelopes["M2"].min_steps = 3
    
    memory = InMemorySaver()
    wrapped_checkpointer = DHMCWrappedCheckpointer(
        underlying=memory,
        dhmc_instance=dhmc_instance,
        node_to_module=node_to_module,
        node_to_step_type=node_to_step_type,
    )
    
    graph = builder.compile(checkpointer=wrapped_checkpointer)
    
    config = {"configurable": {"thread_id": "loan-inject-thread"}}
    initial_state = {
        "query": "Normal loan application.",
        "applicant_name": "Normal Applicant",
        "requested_amount": 30000,
        "loan_type": "personal",
    }
    
    graph.invoke(initial_state, config)
    
    # Audit should catch the deviation
    auditor = DHMCAuditor()
    report = auditor.audit(dhmc_instance)
    report.print_report()


def scenario_subagent():
    print("\n" + "="*60)
    print("SCENARIO 4: Recursive Sub-Agent Provenance in LangGraph")
    print("="*60)
    
    global shared_parent_wrapper
    
    # 1. Build Parent Graph
    parent_builder = StateGraph(LoanState)
    parent_builder.add_node("intent_parser", node_intent_parser)
    parent_builder.add_node("bureau_lookup_agent", node_bureau_lookup_agent)
    parent_builder.add_node("synthesis", node_synthesis)
    
    parent_builder.add_edge(START, "intent_parser")
    parent_builder.add_edge("intent_parser", "bureau_lookup_agent")
    parent_builder.add_edge("bureau_lookup_agent", "synthesis")
    parent_builder.add_edge("synthesis", END)
    
    parent_dhmc = build_dhmc("loan-subagent-001")
    # In Scenario 4, M2 envelope needs to allow SUBAGENT step type
    parent_dhmc.envelopes["M2"].allowed_types.add(StepType.SUBAGENT)
    # Scenario 4 has 1 step in M2 (the bureau_lookup_agent), so we set min_steps=1
    parent_dhmc.envelopes["M2"].min_steps = 1
    
    parent_memory = InMemorySaver()
    parent_wrapper = DHMCWrappedCheckpointer(
        underlying=parent_memory,
        dhmc_instance=parent_dhmc,
        node_to_module=node_to_module,
        node_to_step_type=node_to_step_type,
    )
    
    # Expose wrapper globally so the parent node can access it
    shared_parent_wrapper = parent_wrapper
    
    parent_graph = parent_builder.compile(checkpointer=parent_wrapper)
    
    # 2. Run Parent Graph
    parent_config = {"configurable": {"thread_id": "parent-thread"}}
    print("\n[Pregel] Starting real parent LangGraph loop...")
    parent_graph.invoke(
        {
            "query": "High-net-worth loan request.",
            "applicant_name": "Wealthy Investor",
            "requested_amount": 1000000,
            "loan_type": "personal",
        },
        parent_config
    )
    print("[Pregel] Parent LangGraph loop finished.")
    
    # 3. Audit parent dhmc
    auditor = DHMCAuditor()
    report = auditor.audit(parent_dhmc)
    report.print_report()


if __name__ == "__main__":
    scenario_clean()
    scenario_context_hijack()
    scenario_unauthorized_step()
    scenario_subagent()
    print("\n" + "="*60)
    print("LANGGRAPH DHMC MONITORED PIPELINE COMPLETE — All four scenarios demonstrated")
    print("="*60)
