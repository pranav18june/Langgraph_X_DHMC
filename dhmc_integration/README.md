# DHMC LangGraph Cryptographic Provenance Integration

This directory contains the integration of **DHMC (Dynamic Hierarchical Merkle-Chain)** into the **LangGraph** multi-agent LLM workflow orchestrator.

This integration is completely **additive** and does not modify any core LangGraph engine code or StateGraph definitions. It operates entirely as a transparent interceptor wrapper over LangGraph's base checkpointer saver.

---

## Installation & Requirements

The DHMC implementation is designed for maximum speed, security, and portability, using **only Python standard library packages** (`hashlib`, `json`, `os`, `uuid`, `hmac`, `dataclasses`).

No external pip dependencies are required for DHMC.

---

## How to Run the Demo

To run the complete multi-scenario LangGraph demonstration, execute the following command from the repository root:

```bash
PYTHONPATH=libs/checkpoint:libs/langgraph:libs/prebuilt:. python dhmc_integration/loan_pipeline_demo.py
```

### Expected Output
The demo executes real StateGraph nodes, routing, and transitions under `MemorySaver` (InMemorySaver) checkpointing. It will output four detailed test scenarios:

1. **SCENARIO 1: Clean Execution**
   - Resolves a standard personal loan request.
   - Outputs the final forensic audit report with a `CLEAN` verdict, showing that all leaves, nonces, and module hashes verified perfectly.

2. **SCENARIO 2: Context Hijack (Post-Execution CAS Tampering)**
   - Executes a legitimate loan application, then simulates a post-execution attacker modifying the credit score report in the Content-Addressable Storage (CAS) (bypassing graph execution).
   - The forensic auditor detects the tamper, prints a `TAMPERED` verdict, and **localizes the breach precisely to the step** `M2:step:0000` (credit score retrieval).

3. **SCENARIO 3: Unauthorized Step (Envelope Violation)**
   - Executes the graph including an unauthorized `database_write` node.
   - The checkpointer wrapper intercepts the step, compares the step type with `M2`'s policy boundary, and flags a conformance deviation (`POLICY_VIOLATION` verdict).

4. **SCENARIO 4: Recursive Sub-Agent Provenance**
   - Demonstrates a parent graph spawning a child checkpointer for a sub-graph bureau lookup.
   - Executes the sub-graph cleanly, gets co-signed attestation tokens, and collapses the child chain back into the parent MMR as a single parent leaf.

---

## Adding DHMC to Your Own LangGraph Application

To implement DHMC cryptographic provenance tracking in your own LangGraph pipeline, you only need to touch **three files**:

1. **`dhmc_langgraph_wrapper.py`**:
   - Copy this transparent wrapper class into your project.

2. **Define Schema Envelopes**:
   - Initialize the `DHMCCheckpointer` with policy boundaries (min/max steps, allowed StepTypes, and permitted branch/conditional targets) for each macro-module.

3. **Graph Compilation**:
   - Instead of compiling your graph with `MemorySaver()` or `SqliteSaver()`, pass them wrapped inside `DHMCWrappedCheckpointer`:
   ```python
   base_checkpointer = SqliteSaver.from_conn_string("state.db")
   dhmc_instance = DHMCCheckpointer(session_id="session-123", envelopes={...})
   
   wrapped_checkpointer = DHMCWrappedCheckpointer(
       underlying=base_checkpointer,
       dhmc_instance=dhmc_instance,
       node_to_module={
           "intent_parser": "M1",
           "credit_lookup": "M2",
           "decision_maker": "M3"
       },
       node_to_step_type={
           "intent_parser": StepType.LLM,
           "credit_lookup": StepType.RAG,
           "decision_maker": StepType.LLM
       }
   )
   
   graph = builder.compile(checkpointer=wrapped_checkpointer)
   ```

---

## Known Limitations

- **Simulated TEE**: Nonces are generated using `os.urandom(32)` representing simulated secure enclave hardware entropy. For production-grade security against nonce prediction, replace `SimulatedTEEEnclave` calls with actual hardware enclave calls (e.g., Intel SGX/AWS Nitro Unix socket interface).
- **In-Memory CAS**: The content-addressed storage (CAS) is simulated inside a memory dictionary (`cas_store`). In production, this should be backed by a persistent content-addressable storage layer (like IPFS, S3, or a secure DB).
