/**
 * mockDHMC.js — Simulated DHMC Engine
 * 
 * Runs entirely in the browser. Simulates the core DHMC cryptographic
 * provenance system: step registration, hash chaining, CAS storage,
 * schema envelope validation, and the 7-check forensic audit suite.
 */

// ── SHA-256 based hash function producing 64-char hex strings ──
async function hashData(...parts) {
  const str = parts.map(p => typeof p === 'string' ? p : JSON.stringify(p)).join('|');
  const msgBuffer = new TextEncoder().encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function generateNonce() {
  const arr = new Uint8Array(32);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generateCASUri(payload) {
  const hash = await hashData('cas', payload);
  return `cas://sha256:${hash}`;
}

// ── MockDHMCEngine ──────────────────────────────────────────────
export class MockDHMCEngine {
  constructor(sessionId, envelopes) {
    this.sessionId = sessionId;
    this.envelopes = envelopes; // { M1: { moduleId, minSteps, maxSteps, allowedTypes, allowedBranches? }, ... }
    this.stepRecords = [];
    this.casStore = {}; // uri -> payload
    this.moduleStates = {}; // moduleId -> { stepCount, closed, moduleHash, mmrLeaves }
    this.monotonicCounter = 0;
    this.prevModuleHash = '0'.repeat(64);
    
    // Initialize module states
    for (const [modId, env] of Object.entries(envelopes)) {
      this.moduleStates[modId] = {
        stepCount: 0,
        closed: false,
        moduleHash: null,
        mmrLeaves: [],
      };
    }
  }

  async registerStep(moduleId, stepType, inputPayload, outputPayload, branchId = null) {
    const envelope = this.envelopes[moduleId];
    const modState = this.moduleStates[moduleId];
    
    if (!modState) {
      throw new Error(`Unknown module: ${moduleId}`);
    }
    
    const stepIndex = modState.stepCount;
    const stepId = `${moduleId}:step:${String(stepIndex).padStart(4, '0')}`;
    const timestamp = new Date().toISOString();
    const nonce = generateNonce();
    
    // Store payloads in CAS
    const inputCasUri = await generateCASUri(inputPayload);
    const outputCasUri = await generateCASUri(outputPayload);
    this.casStore[inputCasUri] = JSON.parse(JSON.stringify(inputPayload));
    this.casStore[outputCasUri] = JSON.parse(JSON.stringify(outputPayload));
    
    // Compute hash chain
    const preHash = await hashData(stepId, inputPayload, nonce, this.prevModuleHash);
    const postHash = await hashData(stepId, outputPayload, preHash);
    const binding = await hashData(preHash, postHash);
    
    // Validate against envelope
    let deviation = null;
    if (envelope && !envelope.allowedTypes.includes(stepType)) {
      deviation = `ENVELOPE_TYPE_VIOLATION: ${stepType} not in [${envelope.allowedTypes.join(', ')}]`;
    }
    if (branchId && envelope && envelope.allowedBranches && !envelope.allowedBranches.includes(branchId)) {
      deviation = `INVALID_BRANCH_ID: ${branchId}`;
    }
    
    this.monotonicCounter++;
    
    const record = {
      stepId,
      moduleId,
      stepType,
      timestamp,
      nonce,
      preHash,
      postHash,
      binding,
      inputCasUri,
      outputCasUri,
      monotonicCounter: this.monotonicCounter,
      prevModuleHash: this.prevModuleHash,
      deviation,
      branchId,
    };
    
    this.stepRecords.push(record);
    modState.stepCount++;
    modState.mmrLeaves.push(binding);
    
    return record;
  }

  async closeModule(moduleId) {
    const modState = this.moduleStates[moduleId];
    if (!modState || modState.closed) return;
    
    // Compute MMR peak (simplified: hash all leaves together)
    const mmrPeak = modState.mmrLeaves.length > 0
      ? await hashData('mmr_peak', ...modState.mmrLeaves)
      : '0'.repeat(64);
    
    // Module hash = H(prevModuleHash || mmrPeak || stepCount)
    const moduleHash = await hashData(this.prevModuleHash, mmrPeak, modState.stepCount);
    modState.moduleHash = moduleHash;
    modState.mmrPeak = mmrPeak;
    modState.closed = true;
    
    // Chain modules
    this.prevModuleHash = moduleHash;
  }

  simulateTamper(stepIndex) {
    if (stepIndex >= this.stepRecords.length) return;
    const record = this.stepRecords[stepIndex];
    
    // Tamper the output CAS entry — modify the stored payload
    const uri = record.outputCasUri;
    if (this.casStore[uri]) {
      const tampered = { ...this.casStore[uri], credit_policy: 'credit_threshold: 100', _tampered: true };
      this.casStore[uri] = tampered;
    }
  }

  getStepRecords() {
    return this.stepRecords;
  }

  getCASEntries() {
    return Object.entries(this.casStore).map(([uri, payload]) => ({
      uri,
      payload,
      preview: JSON.stringify(payload).substring(0, 120),
    }));
  }

  exportChain() {
    return {
      sessionId: this.sessionId,
      modules: Object.fromEntries(
        Object.entries(this.moduleStates).map(([id, state]) => [
          id,
          {
            moduleId: id,
            stepCount: state.stepCount,
            moduleHash: state.moduleHash,
            mmrPeak: state.mmrPeak || null,
            closed: state.closed,
          },
        ])
      ),
      totalSteps: this.stepRecords.length,
      finalHash: this.prevModuleHash,
    };
  }
}

// ── 7-Check Forensic Audit Suite ────────────────────────────────
export async function runAudit(engine) {
  const chain = engine.exportChain();
  const findings = [];
  let verdict = 'CLEAN';
  let breachStep = null;

  // ── Check 1: Schema Envelope Conformance ──
  for (const [modId, modData] of Object.entries(chain.modules)) {
    const envelope = engine.envelopes[modId];
    if (!envelope) continue;
    const count = modData.stepCount;
    const inRange = count >= envelope.minSteps && count <= envelope.maxSteps;
    findings.push({
      check: `Schema Envelope Conformance [${modId}]`,
      passed: inRange,
      detail: inRange
        ? `Step count ${count} within [${envelope.minSteps}, ${envelope.maxSteps}]`
        : `Step count ${count} outside [${envelope.minSteps}, ${envelope.maxSteps}]`,
      moduleId: modId,
    });
    if (!inRange) verdict = 'POLICY_VIOLATION';
  }

  // ── Check 2: Nonce Uniqueness ──
  const seenNonces = new Set();
  let nonceCollision = false;
  for (const step of engine.stepRecords) {
    if (seenNonces.has(step.nonce)) {
      findings.push({
        check: 'Nonce Uniqueness',
        passed: false,
        detail: `Duplicate nonce at step ${step.stepId}`,
        stepId: step.stepId,
        evidence: { duplicateNonce: step.nonce },
      });
      nonceCollision = true;
      verdict = 'TAMPERED';
    }
    seenNonces.add(step.nonce);
  }
  if (!nonceCollision) {
    findings.push({
      check: 'Nonce Uniqueness',
      passed: true,
      detail: `All ${seenNonces.size} nonces unique`,
    });
  }

  // ── Check 3: Deviation Record Review ──
  const deviations = engine.stepRecords.filter(s => s.deviation);
  if (deviations.length > 0) {
    for (const d of deviations) {
      findings.push({
        check: 'Deviation Record Review',
        passed: false,
        detail: `Deviation at ${d.stepId}: ${d.deviation}`,
        stepId: d.stepId,
        evidence: { deviationCode: d.deviation },
      });
    }
    if (verdict === 'CLEAN') verdict = 'POLICY_VIOLATION';
  } else {
    findings.push({
      check: 'Deviation Record Review',
      passed: true,
      detail: 'No deviations recorded',
    });
  }

  // ── Check 4: Leaf Hash Recomputation ──
  let tamperFound = false;
  for (const step of engine.stepRecords) {
    const inputPayload = engine.casStore[step.inputCasUri];
    const outputPayload = engine.casStore[step.outputCasUri];

    if (!inputPayload || !outputPayload) {
      findings.push({
        check: `Leaf Hash Recomputation [${step.stepId}]`,
        passed: false,
        detail: 'CAS payload missing — possible payload deletion attack',
        stepId: step.stepId,
      });
      verdict = 'TAMPERED';
      tamperFound = true;
      if (!breachStep) breachStep = step.stepId;
      continue;
    }

    // Recompute
    const rePreHash = await hashData(step.stepId, inputPayload, step.nonce, step.prevModuleHash);
    const rePostHash = await hashData(step.stepId, outputPayload, rePreHash);
    const reBinding = await hashData(rePreHash, rePostHash);

    if (reBinding !== step.binding) {
      findings.push({
        check: `Leaf Hash Recomputation [${step.stepId}]`,
        passed: false,
        detail: 'Binding mismatch — payload tampered after execution',
        stepId: step.stepId,
        evidence: {
          storedBinding: step.binding.substring(0, 32) + '...',
          recomputedBinding: reBinding.substring(0, 32) + '...',
          inputCasUri: step.inputCasUri,
          outputCasUri: step.outputCasUri,
        },
      });
      verdict = 'TAMPERED';
      tamperFound = true;
      if (!breachStep) breachStep = step.stepId;
    }
  }
  if (!tamperFound) {
    findings.push({
      check: 'Leaf Hash Recomputation (all steps)',
      passed: true,
      detail: `All ${engine.stepRecords.length} leaf hashes verified`,
    });
  }

  // ── Check 5: Monotonic Counter Ordering ──
  const counters = engine.stepRecords.map(s => s.monotonicCounter);
  const counterOk = counters.every((c, i) => i === 0 || c > counters[i - 1]);
  findings.push({
    check: 'Monotonic Counter Ordering',
    passed: counterOk,
    detail: counterOk
      ? 'Counters strictly increasing'
      : 'Counter regression detected — replay suspected',
  });
  if (!counterOk) verdict = 'TAMPERED';

  // ── Check 6: Module Chain Integrity ──
  let chainOk = true;
  for (const [modId, modData] of Object.entries(chain.modules)) {
    if (modData.moduleHash) {
      findings.push({
        check: `Module Chain Linkage [${modId}]`,
        passed: true,
        detail: `Module hash recorded: ${modData.moduleHash.substring(0, 16)}...`,
        moduleId: modId,
      });
    }
  }

  // ── Check 7: CAS Payload Integrity ──
  let casOk = true;
  for (const [uri, payload] of Object.entries(engine.casStore)) {
    const expectedUri = await generateCASUri(payload);
    if (uri !== expectedUri) {
      findings.push({
        check: 'CAS Payload Integrity',
        passed: false,
        detail: `URI mismatch for stored payload`,
        evidence: {
          storedUri: uri.substring(0, 40) + '...',
          recomputedUri: expectedUri.substring(0, 40) + '...',
        },
      });
      casOk = false;
      verdict = 'TAMPERED';
    }
  }
  if (casOk) {
    findings.push({
      check: 'CAS Payload Integrity',
      passed: true,
      detail: `All ${Object.keys(engine.casStore).length} CAS entries verified`,
    });
  }

  return {
    sessionId: chain.sessionId,
    verdict,
    findings,
    breachStep,
  };
}
