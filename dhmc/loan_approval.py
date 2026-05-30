"""
pipeline/loan_approval.py

Reference multi-agent pipeline: automated loan approval.
Simulates LangGraph's Pregel superstep execution model.

Each function below represents a LangGraph node. In real LangGraph:
  - Each node executes during the Execute phase of a superstep
  - Writes go to checkpoint_pending_writes buffer
  - after_tick() applies writes and calls put_checkpoint()
  - DHMC checkpointer intercepts put_writes() and put()

Here we simulate the same data flow explicitly to demonstrate
the integration points without requiring a full LangGraph install.

Macro-modules:
  M1 — Query Intent Parsing          (LLM node)
  M2 — Async Multi-Source Evaluation (RAG + TOOL nodes, dynamic 3-5 steps)
  M3 — Synthesis and Decision        (LLM + SYNTHESIS nodes)
"""

import time
import random
from typing import Any, Dict, Optional


# ── Simulated LangGraph node functions ────────────────────────────────────────
# In real LangGraph these would be decorated with @dhmc_node wrapper.
# The DHMC checkpointer captures their input (channel_values before execution)
# and output (writes applied after execution) at the superstep boundary.

def node_intent_parser(state: dict) -> dict:
    """M1: Parse applicant query, extract structured parameters."""
    applicant_query = state.get("query", "")
    return {
        "applicant_name":   state.get("applicant_name", "Unknown"),
        "requested_amount": state.get("requested_amount", 50000),
        "loan_type":        state.get("loan_type", "personal"),
        "parsed_intent":    f"Loan request parsed: {applicant_query[:80]}",
    }


def node_credit_score_retrieval(state: dict) -> dict:
    """M2 step 1: RAG — retrieve credit score from external bureau."""
    # Simulates retrieval of a credit policy document
    # In an attack scenario, this document might be substituted
    return {
        "credit_score":   state.get("_injected_score", 720),  # controlled for attack simulation
        "credit_policy":  "credit_threshold: 650",
        "bureau_source":  "Equifax",
        "retrieval_doc_hash": "sha256:abc123authorized",
    }


def node_income_verification(state: dict) -> dict:
    """M2 step 2: TOOL — invoke income verification service."""
    return {
        "monthly_income":    8500,
        "employment_status": "VERIFIED",
        "employer":          "Acme Corp",
        "verification_ref":  f"IVR-{int(time.time())}",
    }


def node_ofac_lookup(state: dict) -> dict:
    """M2 step 3: TOOL — OFAC sanctions lookup."""
    return {
        "ofac_status":  "CLEAR",
        "checked_at":   time.time(),
        "list_version": "2026-05-29",
    }


def node_fraud_check(state: dict) -> dict:
    """
    M2 step 4 (CONDITIONAL): invoked only when risk score > threshold.
    This is the dynamic step count — 3 or 4 steps in M2 depending on runtime signals.
    Maps to LangGraph's conditional edges and EphemeralValue channels.
    """
    return {
        "fraud_risk_score": 0.12,
        "fraud_signals":    [],
        "recommendation":   "PROCEED",
    }


def node_synthesis(state: dict) -> dict:
    """M3: LLM synthesizes all signals into final decision."""
    credit_score = state.get("credit_score", 0)
    threshold = 650
    amount = state.get("requested_amount", 50000)
    income = state.get("monthly_income", 0)

    approved = (
        credit_score >= threshold
        and state.get("employment_status") == "VERIFIED"
        and state.get("ofac_status") == "CLEAR"
        and (amount / max(income, 1)) < 10
    )

    return {
        "decision":    "APPROVED" if approved else "DECLINED",
        "credit_score_used":   credit_score,
        "threshold_applied":   threshold,
        "reason": (
            f"Credit score {credit_score} meets threshold {threshold}; "
            f"income verified; OFAC clear."
            if approved else
            f"Credit score {credit_score} below threshold {threshold} "
            f"or income insufficient."
        ),
    }


# ── Pipeline orchestrator ──────────────────────────────────────────────────────

def run_loan_approval_pipeline(
    applicant_query: str,
    applicant_name: str,
    requested_amount: int,
    dhmc,
    inject_attack: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the loan approval pipeline with DHMC provenance tracking.

    inject_attack options (for evaluation):
      "context_hijack"      — substitute credit score document (M2 step 1)
      "unauthorized_step"   — inject database_write step (M2)
      "replay"              — simulate stale nonce reuse
      None                  — clean execution
    """
    from dhmc.schema_envelope import StepType, DeviationCode
    from dhmc.langgraph_checkpointer import DHMCCheckpointer

    state = {
        "query":            applicant_query,
        "applicant_name":   applicant_name,
        "requested_amount": requested_amount,
        "loan_type":        "personal",
    }

    print(f"\n{'─'*55}")
    print(f"PIPELINE START  |  applicant={applicant_name}")
    print(f"attack={inject_attack or 'none'}")
    print(f"{'─'*55}")

    # ── MACRO-MODULE M1: Intent Parsing ────────────────────────────────────
    print("\n[M1] Intent Parsing")
    input_state = dict(state)
    output = node_intent_parser(state)
    state.update(output)

    dhmc.register_step(
        module_id="M1",
        step_type=StepType.LLM,
        input_payload=input_state,
        output_payload=output,
    )
    dhmc.close_module("M1")

    # ── MACRO-MODULE M2: Multi-Source Evaluation ───────────────────────────
    print("\n[M2] Multi-Source Evaluation")

    # Step 1: Credit score retrieval (potential attack point)
    if inject_attack == "context_hijack":
        # Attacker substitutes credit policy document: threshold 650 → 100
        state["_injected_score"] = 150  # low score applicant
        input_m2s1 = dict(state)
        output_m2s1 = node_credit_score_retrieval(state)
        # Attacker modifies the output to look like approved threshold was met
        output_m2s1_tampered = dict(output_m2s1)
        output_m2s1_tampered["credit_policy"] = "credit_threshold: 100"  # tampered
        output_m2s1_tampered["credit_score"] = 150
        state.update(output_m2s1_tampered)
        # DHMC sees the real document hash mismatch
        rec = dhmc.register_step("M2", StepType.RAG, input_m2s1, output_m2s1_tampered)
        print(f"  [ATTACK] Context hijack injected at M2:step:0 | deviation={rec.deviation}")
    else:
        input_m2s1 = dict(state)
        output_m2s1 = node_credit_score_retrieval(state)
        state.update(output_m2s1)
        dhmc.register_step("M2", StepType.RAG, input_m2s1, output_m2s1)

    # Step 2: Income verification
    input_m2s2 = dict(state)
    output_m2s2 = node_income_verification(state)
    state.update(output_m2s2)
    dhmc.register_step("M2", StepType.TOOL, input_m2s2, output_m2s2)

    # Step 3: OFAC lookup
    input_m2s3 = dict(state)
    output_m2s3 = node_ofac_lookup(state)
    state.update(output_m2s3)
    dhmc.register_step("M2", StepType.TOOL, input_m2s3, output_m2s3)

    # Unauthorized step injection (attack simulation)
    if inject_attack == "unauthorized_step":
        print("  [ATTACK] Injecting unauthorized 'database_write' step")
        # "database_write" is not in M2's allowed_types envelope
        rec = dhmc.register_step(
            "M2", StepType.TOOL,  # This would be a custom "database_write" type
            {"action": "database_write", "target": "loan_decisions"},
            {"rows_modified": 47},
        )
        print(f"  [DHMC] Deviation detected: {rec.deviation}")

    # Conditional step: fraud check (dynamic topology — the key DHMC claim)
    risk_score = random.random()
    if risk_score > 0.4 or inject_attack == "context_hijack":
        print(f"  [M2] Risk signal {risk_score:.2f} > 0.4 — triggering fraud check (dynamic step)")
        input_m2s4 = dict(state)
        output_m2s4 = node_fraud_check(state)
        state.update(output_m2s4)
        dhmc.register_step(
            "M2", StepType.VALIDATION, input_m2s4, output_m2s4,
            branch_id="fraud_check",
        )

    dhmc.close_module("M2")

    # ── MACRO-MODULE M3: Synthesis & Decision ─────────────────────────────
    print("\n[M3] Synthesis & Decision")
    input_m3 = dict(state)
    output_m3 = node_synthesis(state)
    state.update(output_m3)
    dhmc.register_step("M3", StepType.LLM, input_m3, output_m3)
    dhmc.close_module("M3")

    print(f"\n{'─'*55}")
    print(f"PIPELINE COMPLETE | decision={state.get('decision')} | "
          f"credit_score_used={state.get('credit_score_used')}")
    print(f"{'─'*55}\n")

    return state
