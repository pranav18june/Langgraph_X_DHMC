import { useMemo } from 'react';
import {
  Brain, Database, Wrench, Shield, GitBranch, Sparkles, AlertTriangle
} from 'lucide-react';
import './PipelineVisualizer.css';

const STEP_ICONS = {
  llm: Brain,
  rag: Database,
  tool: Wrench,
  validation: Shield,
  subagent: GitBranch,
  synthesis: Sparkles,
  // uppercase variants
  LLM: Brain,
  RAG: Database,
  TOOL: Wrench,
  VALIDATION: Shield,
  SUBAGENT: GitBranch,
  SYNTHESIS: Sparkles,
};

const MODULE_META = {
  M1: { label: 'Intent Parsing', cssClass: 'm1' },
  M2: { label: 'Evaluation', cssClass: 'm2' },
  M3: { label: 'Decision', cssClass: 'm3' },
};

function getModuleStatus(steps) {
  if (steps.some(s => s.status === 'failed')) return 'has-failure';
  if (steps.some(s => s.status === 'running')) return 'active';
  if (steps.every(s => s.status === 'complete')) return 'completed';
  return '';
}

function getOverallStatus(steps) {
  if (!steps || steps.length === 0) return null;
  if (steps.some(s => s.status === 'failed')) return 'failed';
  if (steps.every(s => s.status === 'complete')) return 'complete';
  if (steps.some(s => s.status === 'running')) return 'running';
  return 'pending';
}

function StepNode({ step, globalIndex, onClick }) {
  const Icon = STEP_ICONS[step.stepType] || Wrench;

  return (
    <div
      className={`step-node${step.isAttack ? ' attack' : ''}`}
      onClick={() => onClick && onClick(step, globalIndex)}
      title={step.description || step.nodeName}
    >
      <div className={`step-circle ${step.status}`}>
        <Icon className="step-icon" />
        <span className={`status-dot ${step.status}`} />
        {step.isAttack && (
          <span className="attack-badge">
            <AlertTriangle />
          </span>
        )}
      </div>
      <span className="step-label">{step.nodeName}</span>
      <span className="step-type-badge">{step.stepType}</span>
      {step.isAttack && step.attackDetail && (
        <span className="attack-tooltip">{step.attackDetail}</span>
      )}
    </div>
  );
}

function ModuleCard({ moduleId, steps, globalIndexOffset, activeStepIndex, onStepClick }) {
  const meta = MODULE_META[moduleId] || { label: moduleId, cssClass: '' };
  const moduleStatus = getModuleStatus(steps);

  return (
    <div className={`pipeline-module ${meta.cssClass} ${moduleStatus}`}>
      <div className="module-header">
        <span className="module-id-badge">{moduleId}</span>
        <span className="module-name">{meta.label}</span>
      </div>
      <div className="module-steps">
        {steps.map((step, i) => {
          const globalIdx = globalIndexOffset + i;
          const connectorStatus =
            step.status === 'complete' ? 'completed' :
            step.status === 'running' ? 'active' : '';

          return (
            <div key={step.nodeId || globalIdx} style={{ display: 'contents' }}>
              {i > 0 && (
                <div className={`step-connector ${connectorStatus}`}>
                  <div className="step-connector-line" />
                </div>
              )}
              <StepNode
                step={step}
                globalIndex={globalIdx}
                onClick={onStepClick}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function PipelineVisualizer({ steps = [], activeStepIndex = -1, onStepClick }) {
  const modules = useMemo(() => {
    const grouped = [];
    const seen = new Map();
    steps.forEach((step, idx) => {
      const mid = step.moduleId || 'M?';
      if (!seen.has(mid)) {
        seen.set(mid, grouped.length);
        grouped.push({ moduleId: mid, steps: [], startIndex: idx });
      }
      grouped[seen.get(mid)].steps.push(step);
    });
    return grouped;
  }, [steps]);

  const overallStatus = getOverallStatus(steps);

  if (!steps || steps.length === 0) {
    return (
      <div className="pipeline-visualizer">
        <div className="pipeline-empty">Select a scenario and click Run to visualize the pipeline</div>
      </div>
    );
  }

  return (
    <div className="pipeline-visualizer">
      <div className="pipeline-header">
        <h3>Pipeline Execution</h3>
        {overallStatus && (
          <span className={`pipeline-status-badge ${overallStatus}`}>
            {overallStatus === 'complete' ? '✓ Complete' :
             overallStatus === 'running' ? '● Running' :
             overallStatus === 'failed' ? '✕ Failed' : '○ Pending'}
          </span>
        )}
      </div>
      <div className="pipeline-modules">
        {modules.map((mod, modIdx) => {
          const prevModuleDone = modIdx > 0 &&
            modules[modIdx - 1].steps.every(s => s.status === 'complete');
          return (
            <div key={mod.moduleId} style={{ display: 'contents' }}>
              {modIdx > 0 && (
                <div className={`module-connector${prevModuleDone ? ' active' : ''}`}>
                  <div className="module-connector-line" />
                </div>
              )}
              <ModuleCard
                moduleId={mod.moduleId}
                steps={mod.steps}
                globalIndexOffset={mod.startIndex}
                activeStepIndex={activeStepIndex}
                onStepClick={onStepClick}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
