import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  GitBranch, ArrowRight, Play, MousePointerClick,
  ShieldCheck, ShieldX, ChevronRight, Database, Layers,
  Link as LinkIcon, Hash, FileText
} from 'lucide-react'
import MerkleTree from '../components/MerkleTree'
import './MerkleExplorer.css'

export default function MerkleExplorer() {
  const [stepRecords, setStepRecords] = useState(null)
  const [chainData, setChainData] = useState(null)
  const [casStore, setCasStore] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)

  useEffect(() => {
    const loadData = () => {
      const steps = sessionStorage.getItem('dhmc_step_records')
      const chain = sessionStorage.getItem('dhmc_chain_data')
      const cas = sessionStorage.getItem('dhmc_cas_store')
      if (steps) {
        try { setStepRecords(JSON.parse(steps)) } catch { /* ignore */ }
      }
      if (chain) {
        try { setChainData(JSON.parse(chain)) } catch { /* ignore */ }
      }
      if (cas) {
        try { setCasStore(JSON.parse(cas)) } catch { /* ignore */ }
      }
    }

    loadData()
    window.addEventListener('storage', loadData)
    // Custom event for same-tab updates
    window.addEventListener('dhmc-data-updated', loadData)

    return () => {
      window.removeEventListener('storage', loadData)
      window.removeEventListener('dhmc-data-updated', loadData)
    }
  }, [])

  // Convert step records into the format MerkleTree expects
  const merkleSteps = useMemo(() => {
    if (!stepRecords) return []
    return stepRecords.map(s => ({
      bindingHash: s.binding,
      moduleId: s.moduleId,
      nodeName: s.stepId,
      nodeId: s.stepId,
      ...s,
    }))
  }, [stepRecords])

  const hasData = stepRecords || chainData

  if (!hasData) {
    return (
      <div className="explorer page">
        <div className="container">
          <div className="explorer__empty">
            <div className="explorer__empty-icon">
              <GitBranch size={32} />
            </div>
            <h2>No Chain Data Available</h2>
            <p>
              Run a simulation first to generate Merkle chain data.
              The explorer will visualize the full cryptographic chain structure.
            </p>
            <Link to="/simulator" className="explorer__empty-link">
              <Play size={16} />
              Go to Simulator
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Extract modules from chain data
  const moduleEntries = chainData?.modules
    ? Object.entries(chainData.modules).map(([id, mod]) => ({
        id,
        name: id === 'M1' ? 'Intent Parsing' : id === 'M2' ? 'Multi-Source Evaluation' : 'Synthesis & Decision',
        stepCount: mod.stepCount,
        mmrPeak: mod.mmrPeak,
        moduleHash: mod.moduleHash,
      }))
    : []

  // Extract CAS entries
  const casEntries = casStore
    ? casStore.map(entry => ({
        uri: entry.uri,
        payload: JSON.stringify(entry.payload),
        valid: !entry.payload?._tampered,
      }))
    : []

  const abbreviateHash = (hash) => {
    if (!hash) return '—'
    if (hash.length <= 16) return hash
    return `${hash.slice(0, 8)}…${hash.slice(-6)}`
  }

  const handleLeafClick = (step, index) => {
    setSelectedNode(step)
  }

  return (
    <div className="explorer page">
      <div className="container">
        <div className="explorer__header">
          <h1>Merkle Chain Explorer</h1>
          <p>
            Visualize and inspect the cryptographic chain structure from the
            most recent simulation run.
          </p>
        </div>

        {/* Split Panel: Tree + Detail */}
        <div className="explorer__panels">
          <div className="explorer__tree-panel">
            <div className="explorer__tree-panel-title">
              <Layers size={14} />
              Merkle Tree
            </div>
            <MerkleTree
              steps={merkleSteps}
              onLeafClick={handleLeafClick}
            />
          </div>

          <div className="explorer__detail-panel">
            <div className="explorer__detail-title">
              <FileText size={14} />
              Node Details
            </div>

            {!selectedNode ? (
              <div className="explorer__detail-empty">
                <MousePointerClick size={32} />
                <p>Click a node in the tree to<br />view its forensic data</p>
              </div>
            ) : (
              <div className="explorer__detail-fields">
                <div className="explorer__detail-node-header">
                  <span className="explorer__detail-node-name">
                    {selectedNode.stepId || selectedNode.nodeId || 'Node'}
                  </span>
                  {selectedNode.moduleId && (
                    <span className="explorer__detail-node-badge">
                      {selectedNode.moduleId}
                    </span>
                  )}
                </div>

                {selectedNode.stepType && (
                  <div className="explorer__detail-field">
                    <span className="explorer__detail-field-label">Type</span>
                    <span className="explorer__detail-field-value explorer__detail-field-value--text">
                      {selectedNode.stepType}
                    </span>
                  </div>
                )}

                {selectedNode.nonce && (
                  <div className="explorer__detail-field">
                    <span className="explorer__detail-field-label">Nonce</span>
                    <span className="explorer__detail-field-value">
                      {selectedNode.nonce}
                    </span>
                  </div>
                )}

                <div className="explorer__detail-row">
                  {selectedNode.preHash && (
                    <div className="explorer__detail-field">
                      <span className="explorer__detail-field-label">Pre-Hash</span>
                      <span className="explorer__detail-field-value">
                        {selectedNode.preHash}
                      </span>
                    </div>
                  )}
                  {selectedNode.postHash && (
                    <div className="explorer__detail-field">
                      <span className="explorer__detail-field-label">Post-Hash</span>
                      <span className="explorer__detail-field-value">
                        {selectedNode.postHash}
                      </span>
                    </div>
                  )}
                </div>

                {selectedNode.binding && (
                  <div className="explorer__detail-field">
                    <span className="explorer__detail-field-label">Binding Hash</span>
                    <span className="explorer__detail-field-value">
                      {selectedNode.binding}
                    </span>
                  </div>
                )}

                <div className="explorer__detail-row">
                  {selectedNode.inputCasUri && (
                    <div className="explorer__detail-field">
                      <span className="explorer__detail-field-label">Input CAS URI</span>
                      <span className="explorer__detail-field-value">
                        {selectedNode.inputCasUri}
                      </span>
                    </div>
                  )}
                  {selectedNode.outputCasUri && (
                    <div className="explorer__detail-field">
                      <span className="explorer__detail-field-label">Output CAS URI</span>
                      <span className="explorer__detail-field-value">
                        {selectedNode.outputCasUri}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Module Chain Overview */}
        {moduleEntries.length > 0 && (
          <div className="explorer__section">
            <h2 className="explorer__section-title">
              <LinkIcon size={20} />
              Chain Overview
            </h2>

            <div className="explorer__module-chain">
              {moduleEntries.map((mod, i) => (
                <div key={mod.id} style={{ display: 'flex', alignItems: 'center' }}>
                  {i > 0 && (
                    <div className="explorer__module-arrow">
                      <div className="explorer__module-arrow-line">
                        <ChevronRight size={18} />
                      </div>
                    </div>
                  )}
                  <div className="explorer__module-card">
                    <div className="explorer__module-id">{mod.id}</div>
                    <div className="explorer__module-name">{mod.name}</div>
                    <div className="explorer__module-stats">
                      <div className="explorer__module-stat">
                        <span className="explorer__module-stat-label">Steps</span>
                        <span className="explorer__module-stat-value">{mod.stepCount}</span>
                      </div>
                      {mod.mmrPeak && (
                        <div className="explorer__module-stat">
                          <span className="explorer__module-stat-label">MMR Peak</span>
                          <span className="explorer__module-stat-value">
                            {abbreviateHash(mod.mmrPeak)}
                          </span>
                        </div>
                      )}
                      {mod.moduleHash && (
                        <div className="explorer__module-stat">
                          <span className="explorer__module-stat-label">Module Hash</span>
                          <span className="explorer__module-stat-value">
                            {abbreviateHash(mod.moduleHash)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CAS Browser */}
        {casEntries.length > 0 && (
          <div className="explorer__section">
            <h2 className="explorer__section-title">
              <Database size={20} />
              CAS Browser
            </h2>

            <div className="explorer__cas-table-wrapper">
              <table className="explorer__cas-table">
                <thead>
                  <tr>
                    <th>URI</th>
                    <th>Payload Preview</th>
                    <th>Integrity</th>
                  </tr>
                </thead>
                <tbody>
                  {casEntries.map((entry, i) => (
                    <tr key={i}>
                      <td>
                        <span className="explorer__cas-uri">
                          {abbreviateHash(entry.uri)}
                        </span>
                      </td>
                      <td>
                        <span className="explorer__cas-payload">
                          {entry.payload.length > 80
                            ? entry.payload.slice(0, 80) + '…'
                            : entry.payload}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`explorer__cas-status ${
                            entry.valid
                              ? 'explorer__cas-status--valid'
                              : 'explorer__cas-status--invalid'
                          }`}
                        >
                          {entry.valid ? (
                            <><ShieldCheck size={14} /> Valid</>
                          ) : (
                            <><ShieldX size={14} /> Tampered</>
                          )}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
