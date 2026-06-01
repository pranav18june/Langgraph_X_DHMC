# LangGraph × DHMC: Forensic-Grade Cryptographic Provenance

<div align="center">
  <h3>Secure, Tamper-Proof, and Policy-Bounded Multi-Agent Orchestration</h3>
  <p>An additive, zero-modification security layer that wraps LangGraph checkpointers with a Dynamic Hierarchical Merkle-Chain (DHMC) protocol.</p>
</div>

---

## 📌 Executive Overview

**LangGraph × DHMC** integrates a forensic-grade cryptographic provenance tracking framework into the **LangGraph** Pregel orchestration engine. It enables **verifiable audit trails, dynamic policy validation (Schema Envelopes), and post-execution tamper detection** for multi-agent LLM systems—with **absolutely zero modifications** to the core Pregel engine, agent nodes, or graph topology.

### The Problem it Solves
1. **Log Tampering**: Attackers with database or filesystem access can alter agent execution logs or output states post-hoc to hide malicious behavior.
2. **Policy Drift**: Agents can deviate from standard routing guidelines, executing unauthorized database operations or skipping crucial verification nodes.
3. **Context Hijacking**: Inputs or intermediate state variables can be altered mid-flight to manipulate downstream LLM decisions without breaking agent code.

### The DHMC Solution
By intercepting state transitions at the checkpoint boundary, DHMC constructs an append-only **Merkle Mountain Range (MMR)** and a secure **Inter-Module Hash Chain**. Every execution step is cryptographically bound to its precise inputs, outputs, execution context, and a **hardware TEE-backed secure nonce**.

---

## ⚡ Key Architectural Features

*   **Zero-Modification Hooking**: Integrates seamlessly using the **Decorator Pattern** over LangGraph’s `BaseCheckpointSaver` interface.
*   **Immutable Binding**: Generates cryptographic micro-step assertions:  
    $$\text{PreHash} = \text{BLAKE3}(\text{StepID} \mathbin{\Vert} \text{Input} \mathbin{\Vert} \text{Nonce} \mathbin{\Vert} H(M_{t-1}))$$  
    $$\text{PostHash} = \text{BLAKE3}(\text{StepID} \mathbin{\Vert} \text{Output} \mathbin{\Vert} \text{PreHash})$$  
    $$\text{Binding} = \text{BLAKE3}(\text{PreHash} \oplus \text{PostHash})$$
*   **Hierarchical Verifiable Roots (MMR)**: Leaf bindings are appended to an append-only Merkle Mountain Range per module, reducing full execution state to a single verifiable cryptographic peak in $O(\log N)$ time.
*   **Policy-Bounded Schema Envelopes**: Pre-commit structural policy limits (allowed step types, depth, branches, step count ranges) checked natively at run-time.
*   **Hybrid TEE-Grade Nonces**: Uses a hybrid hardware TEE (Trusted Execution Environment) model. A Master Seed is fetched securely from TEE enclaves to derive micro-step nonces inside user space, achieving **sub-microsecond execution overhead**.
*   **Content-Addressable Storage (CAS)**: Payloads are serialized deterministically and referenced via their secure URI digests (`cas://sha256:hash`), isolating audit trails from physical payload storage.

---

## 📦 Project Layout

```
├── dhmc/                       # Core DHMC cryptographic modules
│   ├── auditor.py              # The 7-check Forensic Audit engine & DFIR drill-down
│   ├── langgraph_checkpointer.py # Core checkpointer registering steps & module chains
│   ├── mmr_engine.py           # Merkle Mountain Range data structure
│   ├── nonce_gen.py            # Simulated TEE Enclave (TRNG & HMAC signature)
│   ├── schema_envelope.py      # Schema envelope validation and deviation tracker
│   └── loan_approval.py        # Loan approval pipeline nodes (RAG, Tool, LLM, etc.)
├── dhmc_integration/           # LangGraph wrapper and execution demo
│   ├── loan_pipeline_demo.py   # Multi-scenario demonstration with LangGraph StateGraph
│   └── README.md               # Quickstart guide for the loan demo
├── dhmc_langgraph_wrapper.py   # The transparent wrapper over BaseCheckpointSaver
├── benchmark.py                # MMR performance micro-benchmarking suite
├── benchmark_results.txt       # Logged performance benchmarks
└── dhmc_evaluation_log.txt     # Logged evaluation traces for the 4 Scenarios
```

---

## 🛠️ Quickstart Guide

### 1. Requirements & Setup
DHMC is designed for extreme portability and speed. It has **zero external pip dependencies** and relies exclusively on Python standard library modules (`hashlib`, `json`, `os`, `uuid`, `hmac`).

Ensure your python environment has LangGraph installed:
```bash
pip install -U langgraph
```

### 2. Run the LangGraph Multi-Scenario Demo
To run the automated, multi-scenario demonstration showing the provenance system in action:
```bash
PYTHONPATH=. python dhmc_integration/loan_pipeline_demo.py
```

---

## 🚀 How to Integrate DHMC into Your LangGraph Pipeline

To add forensic-grade provenance tracking to your own LangGraph system, follow this 3-step integration pattern.

### Step 1: Define Your Schema Envelopes & Module Maps
Group your agent nodes into macro-logical modules and specify allowed step types, boundaries, and branch routing permissions.

```python
from dhmc.schema_envelope import SchemaEnvelope, StepType

# 1. Define Envelopes
envelopes = {
    "M1": SchemaEnvelope(
        module_id="M1",
        min_steps=1, max_steps=3,
        allowed_types={StepType.LLM}
    ),
    "M2": SchemaEnvelope(
        module_id="M2",
        min_steps=3, max_steps=5,
        allowed_types={StepType.RAG, StepType.TOOL, StepType.VALIDATION, StepType.SUBAGENT},
        allowed_branches={"fraud_check", "standard"}
    )
}

# 2. Map your LangGraph Node Names to Modules & Step Types
node_to_module = {
    "intent_parser": "M1",
    "credit_retrieval": "M2",
    "income_verification": "M2",
    "ofac_lookup": "M2"
}

node_to_step_type = {
    "intent_parser": StepType.LLM,
    "credit_retrieval": StepType.RAG,
    "income_verification": StepType.TOOL,
    "ofac_lookup": StepType.TOOL
}
```

### Step 2: Wrap and Compile Your Graph
Instead of passing your raw checkpointer (e.g., `InMemorySaver`, `SqliteSaver`, `PostgresSaver`) directly to the LangGraph compiler, wrap it with `DHMCWrappedCheckpointer`.

```python
from langgraph.checkpoint.memory import MemorySaver
from dhmc_langgraph_wrapper import DHMCWrappedCheckpointer
from dhmc.langgraph_checkpointer import DHMCCheckpointer

# 1. Instantiate the base checkpointer and DHMC engine
base_checkpointer = MemorySaver()
dhmc_engine = DHMCCheckpointer(session_id="session-clean-001", envelopes=envelopes)

# 2. Wrap the checkpointer
wrapped_checkpointer = DHMCWrappedCheckpointer(
    underlying=base_checkpointer,
    dhmc_instance=dhmc_engine,
    node_to_module=node_to_module,
    node_to_step_type=node_to_step_type
)

# 3. Compile the LangGraph builder
graph = builder.compile(checkpointer=wrapped_checkpointer)
```

### Step 3: Run the Forensic Audit Suite
After execution, export the cryptographic proof chain and run the forensic auditor to verify system integrity.

```python
from dhmc.auditor import DHMCAuditor

# Export provenance chain
chain_data = dhmc_engine.export_chain()

# Run the 7-Check Audit Suite
auditor = DHMCAuditor(chain_data)
audit_results = auditor.audit()

print(f"Audit Verdict: {audit_results['verdict']}")
# Outputs: CLEAN, TAMPERED, or POLICY_VIOLATION
```

---

## 🔍 The 7-Check Forensic Audit Suite

The `DHMCAuditor` performs seven independent cryptographic and structural checks over the exported chain data:

| # | Audit Check | Target Attack Vector | Description |
|---|---|---|---|
| **1** | **Schema Envelope Conformance** | Policy bypass / Step manipulation | Checks step counts and boundaries against pre-committed limits |
| **2** | **Nonce Uniqueness** | Replay attacks | Verifies no generated nonce is re-used within a session |
| **3** | **Deviation Record Review** | Dynamic injection attacks | Inspects runtime flags for unauthorized step types or branches |
| **4** | **Leaf Hash Recomputation** | Post-execution log tampering | Re-hashes payloads and nonces to check if bindings match records |
| **5** | **Monotonic Counter Ordering** | State reordering / Step removal | Checks that the TEE sequence counter rises strictly by 1 |
| **6** | **Module Chain Integrity** | Structural state manipulation | Verifies the linkage of the inter-module cryptographic chain |
| **7** | **CAS Payload Integrity** | Content corruption / Out-of-band edits | Re-hashes files in the CAS and compares them to their addresses |

---

## ⚡ Performance Benchmarks & Overhead Analysis

DHMC introduces an **extremely low performance fingerprint**, making it fully viable for high-throughput enterprise pipelines. 

### MMR Throughput (Operations/sec)
Micro-benchmarks measuring append operations to the Merkle Mountain Range show logarithmic time growth ($O(\log N)$ amortized complexity):

| Appended Nodes | Mean Latency per Node | Throughput (ops/sec) |
|---|---|---|
| **1,000** | 0.0020 ms (2 $\mu s$) | **~500,000 ops/sec** |
| **2,000** | 0.0035 ms (3.5 $\mu s$) | **~286,000 ops/sec** |

### Per-Step Latency Overhead Breakdown
Using our **Hybrid Nonce Derivation** approach, the total latency impact of adding DHMC to a standard LangGraph step is **~74 microseconds (0.074 ms)**:

*   **Thread Synchronization & Context Capture**: ~49 $\mu s$ (high-level Python wrapper execution)
*   **CAS Payload Serialization & Hash (SHA-256)**: ~15 $\mu s$
*   **Cryptographic Chaining (Pre/Post/Binding)**: ~6 $\mu s$
*   **Dynamic Nonce Derivation (BLAKE3)**: ~2 $\mu s$
*   **MMR Peak Recalculation**: ~2 $\mu s$

Compared to standard LLM inference (100 ms – 3000 ms), the computational footprint represents **$<0.1\%$** of execution time.

---

## 🛡️ Production Security Recommendations

> [!WARNING]  
> **Simulated TEE**: The `SimulatedTEEEnclave` class simulates TEE features in standard software. In production environments, replace it with secure Unix socket calls fetching random numbers directly from hardware enclaves (e.g., Intel SGX `rdrand` or AWS Nitro Enclave `vsock`).

> [!WARNING]  
> **Persistent CAS**: The default Content-Addressable Storage is in-memory. For production, substitute it with an immutable file storage layer (such as AWS S3 with Object Lock or IPFS).

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](file:///Users/pranav/Downloads/langgraph_X_DHMC/LICENSE) file for details.
