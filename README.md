# LangGraph × DHMC: Forensic-Grade Cryptographic Provenance

<div align="center">
  <h3>Secure, Tamper-Proof, and Policy-Bounded Multi-Agent Orchestration</h3>
  <p>An additive, zero-modification security layer that wraps LangGraph checkpointers with a Dynamic Hierarchical Merkle-Chain (DHMC) protocol, now featuring a full-stack React + FastAPI dashboard.</p>
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

## 🌐 Full-Stack Architecture

The project now includes a complete full-stack forensic auditing dashboard:
* **Frontend (React + Vite)**: A dynamic, glassmorphism-styled UI for real-time visualization of the Merkle Tree, cryptographic pipeline, and audit scenario logs.
* **Backend (FastAPI)**: A robust Python backend orchestrating DHMC audit triggers, wrapped around the LangGraph checkpointer.
* **Infrastructure**: Run the Node.js UI server and the Python backend locally for a seamless development experience.

---

## ⚡ Key Architectural Features

*   **Zero-Modification Hooking**: Integrates seamlessly using the **Decorator Pattern** over LangGraph’s `BaseCheckpointSaver` interface.
*   **Immutable Binding**: Generates cryptographic micro-step assertions.
*   **Hierarchical Verifiable Roots (MMR)**: Leaf bindings are appended to an append-only Merkle Mountain Range per module.
*   **Policy-Bounded Schema Envelopes**: Pre-commit structural policy limits natively at run-time.
*   **Hybrid TEE-Grade Nonces**: Sub-microsecond execution overhead using BLAKE3 and hardware-backed derivation.
*   **Content-Addressable Storage (CAS)**: Payloads are serialized deterministically and referenced via their secure URI digests.

---

## 📦 Project Layout

```text
├── UI/                         # React + Vite Frontend Dashboard
│   ├── src/                    # Frontend source code (Components, Pages, etc.)
│   └── package.json            # Node dependencies
├── dhmc/                       # Core DHMC cryptographic modules
│   ├── auditor.py              # The 7-check Forensic Audit engine
│   ├── langgraph_checkpointer.py # Core checkpointer registering steps
│   ├── mmr_engine.py           # Merkle Mountain Range data structure
│   ├── nonce_gen.py            # Simulated TEE Enclave
│   ├── schema_envelope.py      # Schema envelope validation
│   └── loan_approval.py        # LangGraph nodes and execution definitions
├── api.py                      # FastAPI Backend server
├── dhmc_integration/           # CLI/Script-based execution demo
├── dhmc_langgraph_wrapper.py   # The transparent wrapper over BaseCheckpointSaver
└── requirements.txt            # Python dependencies
```

---

## 🛠️ Quickstart Guide

### Run Full-Stack Locally (Recommended)
The easiest way to experience the DHMC LangGraph integration and visual dashboard is by running the services locally:

1. Clone the repository.
2. Start the Python Backend:
   ```bash
   pip install -r requirements.txt
   uvicorn api:app --reload
   ```
3. Start the Frontend Dashboard:
   ```bash
   cd UI
   npm install
   npm run dev
   ```
4. Open your browser and navigate to the Dashboard UI (typically `http://localhost:5173`).

### Run CLI Demo locally
If you only want to run the python cryptographic library without the UI:
```bash
pip install -r requirements.txt
PYTHONPATH=. python dhmc_integration/loan_pipeline_demo.py
```

---

## 🚀 How to Integrate DHMC into Your LangGraph Pipeline

### Step 1: Define Your Schema Envelopes & Module Maps
```python
from dhmc.schema_envelope import SchemaEnvelope, StepType

envelopes = {
    "M1": SchemaEnvelope(module_id="M1", min_steps=1, max_steps=3, allowed_types={StepType.LLM}),
}
node_to_module = {"intent_parser": "M1"}
node_to_step_type = {"intent_parser": StepType.LLM}
```

### Step 2: Wrap and Compile Your Graph
```python
from langgraph.checkpoint.memory import MemorySaver
from dhmc_langgraph_wrapper import DHMCWrappedCheckpointer
from dhmc.langgraph_checkpointer import DHMCCheckpointer

base_checkpointer = MemorySaver()
dhmc_engine = DHMCCheckpointer(session_id="session-001", envelopes=envelopes)
wrapped_checkpointer = DHMCWrappedCheckpointer(
    underlying=base_checkpointer,
    dhmc_instance=dhmc_engine,
    node_to_module=node_to_module,
    node_to_step_type=node_to_step_type
)

# graph = builder.compile(checkpointer=wrapped_checkpointer)
```

### Step 3: Run the Forensic Audit Suite
```python
from dhmc.auditor import DHMCAuditor

chain_data = dhmc_engine.export_chain()
auditor = DHMCAuditor(chain_data)
audit_results = auditor.audit()

print(f"Audit Verdict: {audit_results['verdict']}")
```

---

## 🔍 The 7-Check Forensic Audit Suite

The `DHMCAuditor` performs seven independent cryptographic and structural checks:
1. **Schema Envelope Conformance**: Checks step counts and boundaries.
2. **Nonce Uniqueness**: Verifies no re-used nonces.
3. **Deviation Record Review**: Inspects runtime flags for unauthorized step types.
4. **Leaf Hash Recomputation**: Re-hashes payloads and nonces to check bindings.
5. **Monotonic Counter Ordering**: Checks the TEE sequence counter rises strictly by 1.
6. **Module Chain Integrity**: Verifies the linkage of the inter-module cryptographic chain.
7. **CAS Payload Integrity**: Re-hashes files in the CAS.

---

## 🛡️ Production Security Recommendations

> [!WARNING]  
> **Simulated TEE**: The `SimulatedTEEEnclave` class simulates TEE features in standard software. Replace it with secure Unix socket calls fetching random numbers from hardware enclaves for production.

> [!WARNING]  
> **Persistent CAS**: For production, substitute the in-memory CAS with an immutable file storage layer (such as AWS S3 with Object Lock or IPFS).

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](file:///Users/pranav/Downloads/langgraph_X_DHMC/LICENSE) file for details.
