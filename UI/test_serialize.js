import { MockDHMCEngine, runAudit } from './src/data/mockDHMC.js';

const engine = new MockDHMCEngine(
  `session-test`,
  {
    M1: { moduleId: 'M1', minSteps: 1, maxSteps: 3, allowedTypes: ['llm'] },
    M2: { moduleId: 'M2', minSteps: 1, maxSteps: 5, allowedTypes: ['rag', 'tool', 'validation', 'subagent'], allowedBranches: ['fraud_check', 'standard'] },
    M3: { moduleId: 'M3', minSteps: 1, maxSteps: 2, allowedTypes: ['llm', 'synthesis'] },
  }
);

await engine.registerStep('M1', 'llm', { test: 1 }, { result: 2 });
await engine.closeModule('M1');
const audit = await runAudit(engine);

try {
  JSON.stringify(audit);
  JSON.stringify(engine.getStepRecords());
  JSON.stringify(engine.exportChain());
  JSON.stringify(engine.getCASEntries());
  console.log("STRINGIFY SUCCESS");
} catch (e) {
  console.error("STRINGIFY ERROR", e);
}
