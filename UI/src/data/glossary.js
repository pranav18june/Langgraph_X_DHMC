/**
 * glossary.js — Non-technical glossary of DHMC terms
 */

export const glossaryTerms = [
  {
    term: 'DHMC',
    icon: '🛡️',
    plainEnglish: 'A tamper-proof security system for AI pipelines. Think of it as a digital notary that stamps every action your AI takes, making it impossible to alter records without being caught.',
    technical: 'Dynamic Hierarchical Merkle-Chain — a cryptographic provenance framework that constructs append-only Merkle Mountain Ranges and inter-module hash chains at checkpoint boundaries to provide forensic-grade tamper detection.',
  },
  {
    term: 'Merkle Mountain Range (MMR)',
    icon: '🌲',
    plainEnglish: 'A special data structure that works like a tamper-proof ledger. Every entry is mathematically linked to the ones before it, so changing any past entry breaks the entire chain.',
    technical: 'An append-only binary tree variant where leaves are progressively merged into peaks of equal height. Provides O(log N) append time and enables efficient inclusion proofs for any historical entry.',
  },
  {
    term: 'Content-Addressable Storage (CAS)',
    icon: '📦',
    plainEnglish: 'A filing system where each document is stored by its fingerprint. If someone changes the document, the fingerprint won\'t match anymore — instantly revealing tampering.',
    technical: 'Storage system where data is referenced by its cryptographic hash digest (URI format: cas://sha256:<hash>). Provides integrity verification by comparing the stored hash against a freshly computed hash of the payload.',
  },
  {
    term: 'Schema Envelope',
    icon: '📋',
    plainEnglish: 'Pre-approved "rules of the road" for each module. Defines what types of actions are allowed, how many steps can be taken, and which branches are permitted. Like a policy document signed before execution.',
    technical: 'A pre-committed policy boundary for a macro-module specifying: min/max step counts, allowed step types (RAG, TOOL, LLM, etc.), max recursion depth, and permitted branch identifiers. Validated at module closure.',
  },
  {
    term: 'Nonce',
    icon: '🎲',
    plainEnglish: 'A random number generated for each step, like a unique serial number. If the same nonce appears twice, it means someone is trying to replay an old action — a red flag.',
    technical: 'A cryptographically unique value derived from hardware entropy (TEE TRNG) XOR\'d with chain state (BLAKE3). Bound to a monotonic counter for replay resistance. Format: 64-character hex string.',
  },
  {
    term: 'TEE (Trusted Execution Environment)',
    icon: '🔐',
    plainEnglish: 'A secure hardware vault inside the processor that generates tamper-proof random numbers. Like having a notary built into the CPU chip itself.',
    technical: 'Isolated hardware enclave (e.g., Intel SGX, AWS Nitro) providing hardware-backed random number generation and secure key derivation. DHMC simulates TEE in software for development.',
  },
  {
    term: 'Binding',
    icon: '🔗',
    plainEnglish: 'The final "receipt" for each step — a unique fingerprint that combines the step\'s input fingerprint and output fingerprint. This becomes a permanent leaf in the Merkle tree.',
    technical: 'Leaf hash appended to the MMR, computed as: Binding = BLAKE3(PreHash ⊕ PostHash). Cryptographically ties a step\'s input state, output state, nonce, and chain history into a single verifiable commitment.',
  },
  {
    term: 'PreHash',
    icon: '⬅️',
    plainEnglish: 'A fingerprint of everything going INTO a step — the input data, a unique random number (nonce), and the entire history of the chain up to this point.',
    technical: 'PreHash = BLAKE3(StepID ‖ Input ‖ Nonce ‖ H(M_{t-1})). Commits the step\'s input state to the preceding chain state before execution begins.',
  },
  {
    term: 'PostHash',
    icon: '➡️',
    plainEnglish: 'A fingerprint of everything coming OUT of a step — the output data combined with the PreHash, ensuring the output is linked to the input.',
    technical: 'PostHash = BLAKE3(StepID ‖ Output ‖ PreHash). Chains the execution output to the pre-committed input state, preventing output substitution attacks.',
  },
  {
    term: 'Forensic Audit',
    icon: '🔍',
    plainEnglish: 'A comprehensive security review that runs 7 independent checks on the entire execution chain. The result is either CLEAN (all good), TAMPERED (someone changed something), or POLICY_VIOLATION (rules were broken).',
    technical: 'The DHMCAuditor runs 7 checks: Schema Conformance, Nonce Uniqueness, Deviation Review, Leaf Hash Recomputation, Monotonic Counter Ordering, Module Chain Integrity, and CAS Payload Integrity.',
  },
  {
    term: 'Module Chain',
    icon: '⛓️',
    plainEnglish: 'Modules (groups of steps) are linked together in sequence. Each module\'s fingerprint includes the previous module\'s fingerprint, creating an unbreakable chain.',
    technical: 'Inter-module cryptographic chain where: H(M_t) = BLAKE3(H(M_{t-1}) ‖ MMR_peak ‖ step_count). Provides hierarchical integrity verification across macro-module boundaries.',
  },
  {
    term: 'Macro-Module',
    icon: '📦',
    plainEnglish: 'A logical group of related pipeline steps. For example, "Credit Evaluation" might include credit score lookup, income verification, and fraud detection — all grouped as one module.',
    technical: 'A logical partition of the execution graph into policy-bounded segments (e.g., M1=Intent Parsing, M2=Multi-Source Evaluation, M3=Decision Synthesis). Each module has its own MMR and schema envelope.',
  },
  {
    term: 'Deviation',
    icon: '⚠️',
    plainEnglish: 'A flag raised when something happens that violates the pre-approved rules — like an unauthorized step type or an unexpected branch. It\'s recorded permanently in the chain.',
    technical: 'Runtime policy violation recorded with a DeviationCode (ENVELOPE_TYPE_VIOLATION, ENVELOPE_COUNT_VIOLATION, INVALID_BRANCH_ID, etc.). Deviations are immutably recorded in step records for audit.',
  },
  {
    term: 'Step Types',
    icon: '🏷️',
    plainEnglish: 'Every pipeline step has a type label: RAG (data retrieval), TOOL (external service call), LLM (AI reasoning), VALIDATION (security check), SYNTHESIS (final combination), or SUBAGENT (child pipeline).',
    technical: 'Enumerated categories: RAG, TOOL, LLM, BRANCH, SUBAGENT, VALIDATION, SYNTHESIS. Used by schema envelopes to restrict which operation types are permitted within each module.',
  },
  {
    term: 'Monotonic Counter',
    icon: '🔢',
    plainEnglish: 'A counter that only goes up — 1, 2, 3, 4... If the numbers ever go backwards or skip, it means someone tampered with the order of steps.',
    technical: 'Strictly increasing integer bound to TEE attestation. Must increment by exactly 1 per step. Any regression or gap indicates step reordering, removal, or replay attack.',
  },
  {
    term: 'BLAKE3',
    icon: '#️⃣',
    plainEnglish: 'A very fast fingerprinting algorithm. It takes any data and produces a unique 64-character code. Even changing one letter produces a completely different code.',
    technical: 'Cryptographic hash function (simulated via SHA3-256 in Python implementation). Produces 256-bit digests at ~1 GB/s throughput. Used for all DHMC hash computations.',
  },
  {
    term: 'Genesis Commitment',
    icon: '🏛️',
    plainEnglish: 'The "founding document" of a session — a signed record of all the rules (schema envelopes) that were agreed upon before any steps execute.',
    technical: 'Signed genesis token containing session_id, query_hash, initial monotonic_counter, and SHA3-256 hashes of all module schema envelopes. Anchors the entire session to pre-committed policy bounds.',
  },
];
