import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Play, RotateCcw, ArrowRight, Shield, Activity,
  CheckCircle2, XCircle, Loader, Database, Trash2,
  Wifi, WifiOff, Clock
} from 'lucide-react'
import ScenarioCard from '../components/ScenarioCard'
import PipelineVisualizer from '../components/PipelineVisualizer'
import LiveLogFeed from '../components/LiveLogFeed'
import VerdictBanner from '../components/VerdictBanner'
import StepDetailModal from '../components/StepDetailModal'
import { scenarios } from '../data/scenarios'
import { MockDHMCEngine, runAudit } from '../data/mockDHMC'
import './Simulator.css'

const STEP_DELAY = 800 // ms between steps

export default function Simulator() {
  const navigate = useNavigate()
  const [selectedScenario, setSelectedScenario] = useState(scenarios[0])
  const [simulationState, setSimulationState] = useState('idle') // idle | running | auditing | complete
  const [steps, setSteps] = useState([])
  const [activeStepIndex, setActiveStepIndex] = useState(-1)
  const [logs, setLogs] = useState([])
  const [auditResults, setAuditResults] = useState(null)
  const [selectedStep, setSelectedStep] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const engineRef = useRef(null)
  const runningRef = useRef(false)

  // Backend persistence states
  const [backendConnected, setBackendConnected] = useState(false)
  const [historyList, setHistoryList] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)

  const API_BASE = 'http://localhost:5001/api'

  // Check backend server health
  const checkBackendHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      if (res.ok) {
        setBackendConnected(true)
        return true
      }
      setBackendConnected(false)
      return false
    } catch (e) {
      setBackendConnected(false)
      return false
    }
  }, [])

  // Load saved history runs from the server
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      if (res.ok) {
        const data = await res.json()
        setHistoryList(data)
      }
    } catch (e) {
      console.warn('Failed to load history:', e)
    }
  }, [])

  // Check health and load history on mount + setup polling
  useEffect(() => {
    const init = async () => {
      const isOnline = await checkBackendHealth()
      if (isOnline) {
        loadHistory()
      }
    }
    init()

    // Poll server health every 8 seconds
    const interval = setInterval(async () => {
      const isOnline = await checkBackendHealth()
      if (isOnline) {
        loadHistory()
      }
    }, 8000)

    return () => clearInterval(interval)
  }, [checkBackendHealth, loadHistory])

  // Initialize steps from selected scenario
  useEffect(() => {
    const scenarioSteps = selectedScenario.steps.map(s => ({
      ...s,
      status: 'pending',
    }))
    setSteps(scenarioSteps)
    setActiveStepIndex(-1)
    setLogs([])
    setAuditResults(null)
    setSimulationState('idle')
    setActiveSessionId(null)
  }, [selectedScenario])

  const addLog = useCallback((message, type = 'info') => {
    setLogs(prev => [...prev, {
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }),
      message,
      type,
    }])
  }, [])

  const resetSimulation = useCallback(() => {
    runningRef.current = false
    setSimulationState('idle')
    setActiveStepIndex(-1)
    setLogs([])
    setAuditResults(null)
    setSteps(selectedScenario.steps.map(s => ({ ...s, status: 'pending' })))
    setActiveSessionId(null)
  }, [selectedScenario])

  // Load a session from backend and reconstruct the simulator state
  const handleLoadSession = useCallback(async (id) => {
    if (simulationState === 'running' || simulationState === 'auditing') return

    try {
      const res = await fetch(`${API_BASE}/sessions/${id}`)
      if (!res.ok) {
        addLog('Failed to retrieve session details from server', 'error')
        return
      }
      const session = await res.json()
      
      // Find matching scenario to sync UI state
      const matchingScenario = scenarios.find(s => s.id === session.scenarioId) || scenarios[0]
      setSelectedScenario(matchingScenario)

      // Reconstruct simulator UI variables
      setActiveSessionId(session.id)
      setSimulationState('complete')
      setAuditResults(session.auditResults)
      setLogs(session.logs || [])
      
      // Reconstruct step records states based on index
      const reconstructedSteps = matchingScenario.steps.map((s, idx) => {
        const record = session.stepRecords[idx]
        return {
          ...s,
          status: record ? (record.deviation ? 'failed' : 'complete') : 'pending',
          record: record || null
        }
      })
      setSteps(reconstructedSteps)
      setActiveStepIndex(reconstructedSteps.length - 1)

      // Re-populate sessionStorage to update AuditDashboard and MerkleExplorer
      sessionStorage.setItem('dhmc_audit_results', JSON.stringify(session.auditResults))
      sessionStorage.setItem('dhmc_step_records', JSON.stringify(session.stepRecords))
      sessionStorage.setItem('dhmc_chain_data', JSON.stringify(session.chainData))
      sessionStorage.setItem('dhmc_cas_store', JSON.stringify(session.casStore))
      
      // Trigger window update event for other React pages to re-render
      window.dispatchEvent(new Event('dhmc-data-updated'))
    } catch (e) {
      console.error('Error loading session:', e)
      addLog('Failed to load session from database', 'error')
    }
  }, [simulationState, addLog])

  // Delete a session from history
  const handleDeleteSession = useCallback(async (e, id) => {
    e.stopPropagation() // Prevent loading the card
    
    if (confirm('Are you sure you want to delete this simulation run from history?')) {
      try {
        const res = await fetch(`${API_BASE}/sessions/${id}`, {
          method: 'DELETE'
        })
        if (res.ok) {
          if (activeSessionId === id) {
            resetSimulation()
            setActiveSessionId(null)
            
            // Clear current sessionStorage
            sessionStorage.removeItem('dhmc_audit_results')
            sessionStorage.removeItem('dhmc_step_records')
            sessionStorage.removeItem('dhmc_chain_data')
            sessionStorage.removeItem('dhmc_cas_store')
            window.dispatchEvent(new Event('dhmc-data-updated'))
          }
          loadHistory()
        }
      } catch (e) {
        console.error('Error deleting session:', e)
      }
    }
  }, [activeSessionId, loadHistory, resetSimulation])

  const runSimulation = useCallback(async () => {
    if (runningRef.current) return
    runningRef.current = true
    setSimulationState('running')
    setAuditResults(null)
    setActiveSessionId(null)

    // Accumulate logs locally to avoid stale closures when posting to the server
    const localLogs = []
    const log = (message, type = 'info') => {
      const formattedTime = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })
      const newLog = { timestamp: formattedTime, message, type }
      localLogs.push(newLog)
      setLogs(prev => [...prev, newLog])
    }

    // Initialize DHMC engine
    const engine = new MockDHMCEngine(
      `session-${selectedScenario.id}-${Date.now()}`,
      {
        M1: { moduleId: 'M1', minSteps: 1, maxSteps: 3, allowedTypes: ['llm'] },
        M2: { moduleId: 'M2', minSteps: 1, maxSteps: 5, allowedTypes: ['rag', 'tool', 'validation', 'subagent'], allowedBranches: ['fraud_check', 'standard'] },
        M3: { moduleId: 'M3', minSteps: 1, maxSteps: 2, allowedTypes: ['llm', 'synthesis'] },
      }
    )
    engineRef.current = engine

    log('═══ DHMC Pipeline Simulation Started ═══', 'info')
    log(`Scenario: ${selectedScenario.title}`, 'info')
    log(`Session ID: ${engine.sessionId}`, 'info')
    log(`Applicant: ${selectedScenario.applicant.name}`, 'info')
    log(`Loan Amount: $${selectedScenario.applicant.amount.toLocaleString()}`, 'info')

    const scenarioSteps = selectedScenario.steps

    // Reset all steps to pending
    setSteps(scenarioSteps.map(s => ({ ...s, status: 'pending' })))

    let currentModule = null

    for (let i = 0; i < scenarioSteps.length; i++) {
      const step = scenarioSteps[i]

      // Module transition logging
      if (step.moduleId !== currentModule) {
        if (currentModule) {
          await engine.closeModule(currentModule)
          log(`Module ${currentModule} closed — chain hash updated`, 'hash')
        }
        currentModule = step.moduleId
        log(`\n── Module ${step.moduleId}: ${getModuleName(step.moduleId)} ──`, 'info')
      }

      // Mark step as running
      setActiveStepIndex(i)
      setSteps(prev => prev.map((s, idx) =>
        idx === i ? { ...s, status: 'running' } : s
      ))

      log(`Executing: ${step.nodeName}`, 'info')

      // Simulate execution delay
      await delay(STEP_DELAY)

      // Register step with DHMC
      const record = await engine.registerStep(
        step.moduleId,
        step.stepType,
        { node: step.nodeId, input: `input_for_${step.nodeId}`, ...selectedScenario.applicant },
        { node: step.nodeId, output: `result_from_${step.nodeId}`, processed: true },
        step.branchId || null
      )

      // Log the cryptographic details
      log(`  StepID: ${record.stepId}`, 'hash')
      log(`  Nonce: ${record.nonce.substring(0, 16)}...`, 'hash')
      log(`  PreHash: ${record.preHash.substring(0, 16)}...`, 'hash')
      log(`  PostHash: ${record.postHash.substring(0, 16)}...`, 'hash')
      log(`  Binding: ${record.binding.substring(0, 16)}...`, 'hash')

      if (record.deviation) {
        log(`  ⚠ DEVIATION: ${record.deviation}`, 'warning')
      }

      if (step.isAttack) {
        log(`  🔴 ATTACK: ${step.attackDetail}`, 'error')
      }

      log(`  ✓ Step registered (counter: ${record.monotonicCounter})`, 'success')

      // Mark step as complete or failed
      setSteps(prev => prev.map((s, idx) =>
        idx === i ? { ...s, status: record.deviation ? 'failed' : 'complete', record } : s
      ))
    }

    // Close last module
    if (currentModule) {
      await engine.closeModule(currentModule)
      log(`Module ${currentModule} closed — chain hash updated`, 'hash')
    }

    // Simulate post-execution tampering for context_hijack scenario
    if (selectedScenario.attackType === 'context_hijack') {
      log('\n── Post-Execution Attack ──', 'error')
      log('Attacker modifying CAS payload for credit_retrieval step...', 'error')
      engine.simulateTamper(1) // Tamper with the second step (credit retrieval)
      log('CAS entry modified: credit_threshold changed 650 → 100', 'error')
    }

    log('\n═══ Pipeline Execution Complete ═══', 'info')

    // Small pause before audit
    await delay(600)

    // Run Audit
    setSimulationState('auditing')
    log('\n═══ Running 7-Check Forensic Audit ═══', 'info')
    await delay(400)

    const audit = await runAudit(engine)
    
    // Log each check with a small delay for dramatic effect
    for (const finding of audit.findings) {
      await delay(300)
      const status = finding.passed ? '✓ PASS' : '✗ FAIL'
      const type = finding.passed ? 'success' : 'error'
      log(`  [${status}] ${finding.check}`, type)
      if (!finding.passed) {
        log(`           ${finding.detail}`, 'warning')
      }
    }

    await delay(400)
    log(`\nVerdict: ${audit.verdict}`, audit.verdict === 'CLEAN' ? 'success' : 'error')
    if (audit.breachStep) {
      log(`Breach localized to: ${audit.breachStep}`, 'error')
    }

    setAuditResults(audit)
    setSimulationState('complete')
    
    const sessionId = engine.sessionId
    setActiveSessionId(sessionId)

    // Store results in sessionStorage for other pages
    const stepRecords = engine.getStepRecords()
    const chainData = engine.exportChain()
    const casStore = engine.getCASEntries()

    try {
      sessionStorage.setItem('dhmc_audit_results', JSON.stringify(audit))
      sessionStorage.setItem('dhmc_step_records', JSON.stringify(stepRecords))
      sessionStorage.setItem('dhmc_chain_data', JSON.stringify(chainData))
      sessionStorage.setItem('dhmc_cas_store', JSON.stringify(casStore))
      window.dispatchEvent(new Event('dhmc-data-updated'))
    } catch (e) {
      // sessionStorage might be full, that's ok
    }

    // Save to backend database if online
    try {
      const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: sessionId,
          sessionId,
          scenarioId: selectedScenario.id,
          scenarioTitle: selectedScenario.title,
          applicantName: selectedScenario.applicant.name,
          loanAmount: selectedScenario.applicant.amount,
          auditResults: audit,
          stepRecords,
          chainData,
          casStore,
          logs: localLogs
        })
      })

      if (response.ok) {
        log('✓ Forensic audit run saved to local database', 'success')
        loadHistory()
      }
    } catch (e) {
      console.warn('Failed to save simulation to backend database:', e)
    }

    runningRef.current = false
  }, [selectedScenario, loadHistory])

  const handleStepClick = useCallback((step) => {
    if (step.record) {
      setSelectedStep(step)
      setModalOpen(true)
    }
  }, [])

  return (
    <div className="simulator page">
      <div className="container">
        <div className="simulator__header">
          <div>
            <h1 className="section-title flex items-center gap-md">
              Pipeline Simulator
              {backendConnected ? (
                <span className="simulator__connection-status simulator__connection-status--online animate-fade-in">
                  <span className="simulator__connection-dot" />
                  Backend Online
                </span>
              ) : (
                <span className="simulator__connection-status simulator__connection-status--offline animate-fade-in">
                  <span className="simulator__connection-dot" />
                  Demo Mode (Local)
                </span>
              )}
            </h1>
            <p className="section-subtitle">
              Select a scenario and watch DHMC protect the loan approval pipeline in real-time.
            </p>
          </div>
          <div className="simulator__header-actions">
            {simulationState === 'idle' && (
              <button className="btn btn--primary" onClick={runSimulation}>
                <Play size={16} />
                Run Simulation
              </button>
            )}
            {simulationState === 'running' && (
              <button className="btn btn--secondary" disabled>
                <Loader size={16} className="spin-icon" />
                Running...
              </button>
            )}
            {simulationState === 'auditing' && (
              <button className="btn btn--secondary" disabled>
                <Shield size={16} className="spin-icon" />
                Auditing...
              </button>
            )}
            {simulationState === 'complete' && (
              <>
                <button className="btn btn--secondary" onClick={resetSimulation}>
                  <RotateCcw size={16} />
                  Reset
                </button>
                <button className="btn btn--primary" onClick={() => navigate('/audit')}>
                  View Full Audit
                  <ArrowRight size={16} />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Scenario Selector */}
        <div className="simulator__scenarios">
          <h3 className="simulator__section-label">Select Scenario</h3>
          <div className="simulator__scenario-grid">
            {scenarios.map(scenario => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                selected={selectedScenario.id === scenario.id}
                onClick={() => {
                  if (simulationState === 'idle' || simulationState === 'complete') {
                    setSelectedScenario(scenario)
                  }
                }}
              />
            ))}
          </div>
        </div>

        {/* Workspace Layout Split */}
        <div className="simulator__workspace">
          {/* Main Simulation Area */}
          <div className="simulator__main">
            {/* Pipeline Visualization */}
            <div className="simulator__pipeline-section">
              <h3 className="simulator__section-label">
                <Activity size={16} />
                Pipeline Execution
              </h3>
              <PipelineVisualizer
                steps={steps}
                activeStepIndex={activeStepIndex}
                onStepClick={handleStepClick}
              />
            </div>

            {/* Verdict Banner (when complete) */}
            {auditResults && (
              <div className="simulator__verdict animate-scale-in">
                <VerdictBanner
                  verdict={auditResults.verdict}
                  sessionId={auditResults.sessionId}
                  breachStep={auditResults.breachStep}
                />
              </div>
            )}

            {/* Live Log Feed */}
            <div className="simulator__log-section">
              <h3 className="simulator__section-label">
                <Shield size={16} />
                DHMC Provenance Log
              </h3>
              <LiveLogFeed logs={logs} />
            </div>
          </div>

          {/* Simulation History Sidebar */}
          <div className="simulator__history-sidebar animate-fade-in-up">
            <div className="simulator__history-header-row">
              <h3 className="simulator__history-title">
                <Clock size={16} />
                Simulation Runs
              </h3>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>
                {historyList.length} total
              </span>
            </div>

            <div className="simulator__history-list">
              {historyList.length === 0 ? (
                <div className="simulator__history-empty">
                  <Database size={24} className="simulator__history-empty-icon" />
                  <p>No saved runs.</p>
                  <p style={{ fontSize: '0.75rem', marginTop: 4 }}>
                    Start a simulation to persist audit history.
                  </p>
                </div>
              ) : (
                historyList.map(run => {
                  const isActive = activeSessionId === run.id
                  const formattedDate = new Date(run.date).toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })
                  return (
                    <div
                      key={run.id}
                      className={`simulator__history-card ${isActive ? 'simulator__history-card--active' : ''}`}
                      onClick={() => handleLoadSession(run.id)}
                    >
                      <div className="simulator__history-card-header">
                        <span className="simulator__history-card-applicant">{run.applicantName}</span>
                        <span className={`badge ${
                          run.verdict === 'CLEAN' ? 'badge--success' : 
                          run.verdict === 'TAMPERED' ? 'badge--danger' : 'badge--warning'
                        }`} style={{ fontSize: '0.65rem', padding: '2px 8px' }}>
                          {run.verdict}
                        </span>
                      </div>
                      <span className="simulator__history-card-scenario">{run.scenarioTitle}</span>
                      <div className="simulator__history-card-meta">
                        <span className="simulator__history-card-amount">${run.loanAmount.toLocaleString()}</span>
                        <span>{formattedDate}</span>
                      </div>
                      <button
                        className="simulator__history-card-delete"
                        onClick={(e) => handleDeleteSession(e, run.id)}
                        title="Delete run from history"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Step Detail Modal */}
      <StepDetailModal
        step={selectedStep}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}

function getModuleName(moduleId) {
  const names = {
    M1: 'Intent Parsing',
    M2: 'Multi-Source Evaluation',
    M3: 'Synthesis & Decision',
  }
  return names[moduleId] || moduleId
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
