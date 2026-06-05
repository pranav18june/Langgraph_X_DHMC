import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Shield, AlertTriangle, ArrowRight,
  Play, Search, Hash, FileWarning
} from 'lucide-react'
import VerdictBanner from '../components/VerdictBanner'
import AuditCheckCard from '../components/AuditCheckCard'
import './AuditDashboard.css'

export default function AuditDashboard() {
  const navigate = useNavigate()
  const [auditData, setAuditData] = useState(null)
  const [stepRecords, setStepRecords] = useState(null)

  useEffect(() => {
    const loadData = () => {
      const raw = sessionStorage.getItem('dhmc_audit_results')
      const steps = sessionStorage.getItem('dhmc_step_records')
      if (raw) {
        try { setAuditData(JSON.parse(raw)) } catch { /* ignore */ }
      }
      if (steps) {
        try { setStepRecords(JSON.parse(steps)) } catch { /* ignore */ }
      }
    }

    loadData()
    window.addEventListener('storage', loadData)
    window.addEventListener('dhmc-data-updated', loadData)

    return () => {
      window.removeEventListener('storage', loadData)
      window.removeEventListener('dhmc-data-updated', loadData)
    }
  }, [])

  // ── Empty state
  if (!auditData) {
    return (
      <div className="audit page">
        <div className="container">
          <div className="audit__empty">
            <div className="audit__empty-icon">
              <Search size={32} />
            </div>
            <h2>No Audit Data Yet</h2>
            <p>
              Run a simulation first to generate forensic audit results.
              The 7-check audit suite will analyze every step in the pipeline.
            </p>
            <Link to="/simulator" className="audit__empty-link">
              <Play size={16} />
              Go to Simulator
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const { verdict, findings, sessionId, breachStep } = auditData
  const isTampered = verdict === 'TAMPERED' || verdict === 'POLICY_VIOLATION'

  // Find the breached step record for drill-down
  const breachedRecord = breachStep && stepRecords
    ? stepRecords.find(s => s.stepId === breachStep)
    : null

  return (
    <div className="audit page">
      <div className="container">
        {/* ── Header */}
        <div className="audit__header">
          <h1>Forensic Audit Results</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
            Session: {sessionId}
          </p>
        </div>

        {/* ── Verdict Banner */}
        <VerdictBanner verdict={verdict} sessionId={sessionId} breachStep={breachStep} />

        {/* ── 7 Audit Checks Grid */}
        <div className="audit__checks-grid">
          {(findings || []).map((finding, i) => (
            <div className="audit__check-slot" key={i}>
              <AuditCheckCard
                index={i}
                check={finding.check}
                passed={finding.passed}
                detail={finding.detail}
                evidence={finding.evidence}
              />
            </div>
          ))}
        </div>

        {/* ── Forensic Drill-Down (only for TAMPERED / POLICY_VIOLATION) */}
        {isTampered && breachedRecord && (
          <div className="audit__drilldown">
            <h2 className="audit__drilldown-title">
              <AlertTriangle size={22} />
              Forensic Drill-Down
            </h2>

            <div className="audit__breach-card">
              <div className="audit__breach-header">
                <span className="audit__breach-step-id">
                  <Hash size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                  {breachedRecord.stepId}
                </span>
                <span className="audit__breach-module">
                  {breachedRecord.moduleId}
                </span>
              </div>

              <div className="audit__breach-details">
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Pre-Hash</span>
                  <span className="audit__breach-field-value">{breachedRecord.preHash}</span>
                </div>
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Post-Hash</span>
                  <span className="audit__breach-field-value">{breachedRecord.postHash}</span>
                </div>
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Binding Hash</span>
                  <span className="audit__breach-field-value">{breachedRecord.binding}</span>
                </div>
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Nonce</span>
                  <span className="audit__breach-field-value">{breachedRecord.nonce}</span>
                </div>
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Input CAS URI</span>
                  <span className="audit__breach-field-value">{breachedRecord.inputCasUri}</span>
                </div>
                <div className="audit__breach-field">
                  <span className="audit__breach-field-label">Output CAS URI</span>
                  <span className="audit__breach-field-value">{breachedRecord.outputCasUri}</span>
                </div>
              </div>

              {breachedRecord.deviation && (
                <div className="audit__breach-detection">
                  <div className="audit__breach-detection-label">
                    <FileWarning size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                    Deviation
                  </div>
                  <div className="audit__breach-detection-text">{breachedRecord.deviation}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Actions */}
        <div className="audit__actions">
          <button
            className="btn btn--primary btn--lg"
            onClick={() => navigate('/simulator')}
          >
            <Play size={18} />
            Run New Simulation
          </button>
        </div>
      </div>
    </div>
  )
}
