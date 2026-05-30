"""
run_demo.py
DHMC POC demonstration.

Runs the loan approval pipeline in three modes:
  1. Clean execution        → audit passes, CLEAN verdict
  2. Context hijack attack  → audit fails, TAMPERED verdict, step localized
  3. Unauthorized step      → POLICY_VIOLATION, step rejected at registration

Also demonstrates the forensic drill-down capability.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dhmc.langgraph_checkpointer import DHMCCheckpointer
from dhmc.schema_envelope import SchemaEnvelope, StepType
from dhmc.auditor import DHMCAuditor
from pipeline.loan_approval import run_loan_approval_pipeline


def build_dhmc(session_id: str) -> DHMCCheckpointer:
    """Factory: builds a DHMC instance with the loan approval schema envelopes."""
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
                min_steps=3, max_steps=5,
                allowed_types={StepType.RAG, StepType.TOOL, StepType.VALIDATION},
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


def scenario_clean():
    print("\n" + "="*60)
    print("SCENARIO 1: Clean Execution")
    print("="*60)
    dhmc = build_dhmc("loan-clean-001")
    auditor = DHMCAuditor()

    result = run_loan_approval_pipeline(
        applicant_query="I need a personal loan of $50,000 for home renovation.",
        applicant_name="Rahul Sharma",
        requested_amount=50000,
        dhmc=dhmc,
    )

    report = auditor.audit(dhmc)
    report.print_report()

    chain = dhmc.export_chain()
    total_steps = sum(m["step_count"] for m in chain["modules"].values())
    print(f"Chain summary: {total_steps} total steps | "
          f"{len(chain['cas_uris'])} CAS entries | "
          f"final_hash={chain['final_hash'][:24]}...")


def scenario_context_hijack():
    print("\n" + "="*60)
    print("SCENARIO 2: Context Hijack — Post-Execution CAS Tampering")
    print("Attacker modifies credit document in CAS after clean execution")
    print("="*60)
    dhmc = build_dhmc("loan-attack-hijack-001")
    auditor = DHMCAuditor()

    # Step 1: Pipeline runs CLEANLY — DHMC records legitimate execution
    result = run_loan_approval_pipeline(
        applicant_query="Loan request.",
        applicant_name="Normal Applicant",
        requested_amount=50000,
        dhmc=dhmc,
        inject_attack=None,  # Clean run first
    )

    # Step 2: Attacker with CAS write access tampers the credit document
    # Find the M2 step 0 output URI (credit score retrieval result)
    m2_steps = dhmc.module_states["M2"].steps
    if m2_steps:
        target_step = m2_steps[0]  # Credit score retrieval step
        print(f"\n[ATTACK] Attacker targets M2 step 0 output CAS entry")
        print(f"[ATTACK] URI: {target_step.output_cas_uri}")
        # Attacker modifies the stored credit policy threshold from 650 → 100
        dhmc.simulate_post_execution_tamper(
            target_step.output_cas_uri,
            {   # Modified payload — would have approved a low-score applicant
                "credit_score": 720,
                "credit_policy": "credit_threshold: 100",  # TAMPERED: was 650
                "bureau_source": "Equifax",
                "retrieval_doc_hash": "sha256:abc123authorized",
            }
        )

    # Step 3: Auditor runs — detects the tampered CAS entry
    report = auditor.audit(dhmc)
    report.print_report()

    if report.breach_localized_to:
        print(f"\n[DFIR] Breach localized. Drilling down on: {report.breach_localized_to}")
        evidence = auditor.forensic_drill_down(dhmc, report.breach_localized_to)
        import json
        print(json.dumps(evidence, indent=2, default=str))


def scenario_unauthorized_step():
    print("\n" + "="*60)
    print("SCENARIO 3: Unauthorized Step — Post-Execution Log Injection")
    print("Attacker modifies pipeline input record to hide a step")
    print("="*60)
    dhmc = build_dhmc("loan-attack-inject-001")
    auditor = DHMCAuditor()

    result = run_loan_approval_pipeline(
        applicant_query="Normal loan application.",
        applicant_name="Normal Applicant",
        requested_amount=30000,
        dhmc=dhmc,
        inject_attack=None,
    )

    # Attacker tampers the M1 intent parsing output to change loan amount
    m1_steps = dhmc.module_states["M1"].steps
    if m1_steps:
        target_step = m1_steps[0]
        print(f"\n[ATTACK] Attacker targets M1 output — inflating loan amount in records")
        dhmc.simulate_post_execution_tamper(
            target_step.output_cas_uri,
            {   # Modified: attacker changes the recorded requested amount
                "applicant_name": "Normal Applicant",
                "requested_amount": 500000,  # TAMPERED: was 30000
                "loan_type": "personal",
                "parsed_intent": "Loan request parsed: Normal loan application.",
            }
        )

    report = auditor.audit(dhmc)
    report.print_report()


def scenario_subagent():
    print("\n" + "="*60)
    print("SCENARIO 4: Recursive Sub-Agent Provenance")
    print("="*60)
    dhmc = build_dhmc("loan-subagent-001")

    # Simulate parent pipeline spawning a sub-agent for external credit bureau call
    parent_step_input = {"action": "spawn_credit_bureau_agent", "bureau": "Equifax"}

    # Child sub-agent executes independently with its own DHMC chain
    child_dhmc = dhmc.spawn_subagent_dhmc(
        parent_module_id="M2",
        parent_step_id="M2:credit-bureau-spawn"
    )

    # Child sub-agent runs its own mini-pipeline
    child_dhmc.module_states["sub_M1"] = __import__(
        'dhmc.langgraph_checkpointer', fromlist=['DHMCModuleState']
    ).DHMCModuleState(
        module_id="sub_M1",
        envelope=SchemaEnvelope("sub_M1", 1, 3, {StepType.RAG, StepType.TOOL}),
        mmr=__import__('dhmc.mmr_engine', fromlist=['MerkleMountainRange']).MerkleMountainRange(),
    )
    child_dhmc.envelopes["sub_M1"] = SchemaEnvelope("sub_M1", 1, 3, {StepType.RAG, StepType.TOOL})

    child_dhmc.register_step(
        "sub_M1", StepType.RAG,
        {"query": "credit score lookup Equifax"},
        {"score": 720, "report_id": "EQ-2026-001"},
    )
    child_dhmc.close_module("sub_M1")
    print(f"[Sub-agent] Child chain final hash: {child_dhmc._prev_module_hash.hex()[:24]}...")

    # Collapse sub-agent to single leaf in parent MMR
    collapse_record = dhmc.collapse_subagent(
        parent_module_id="M2",
        step_type=StepType.SUBAGENT,
        child_dhmc=child_dhmc,
        input_payload=parent_step_input,
    )
    print(f"[Parent] Sub-agent collapsed to leaf: {collapse_record.binding.hex()[:24]}...")
    print("[DHMC] ✓ Recursive sub-agent provenance bound to parent MMR")


if __name__ == "__main__":
    scenario_clean()
    scenario_context_hijack()
    scenario_unauthorized_step()
    scenario_subagent()

    print("\n" + "="*60)
    print("POC COMPLETE — All four scenarios demonstrated")
    print("="*60)
