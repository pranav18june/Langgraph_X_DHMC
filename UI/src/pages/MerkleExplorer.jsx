import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  GitBranch, ArrowRight, Play, MousePointerClick,
  ShieldCheck, ShieldX, Database, Layers,
  Link as LinkIcon, FileText, Key, Hash, Link2, Box
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
    window.addEventListener('dhmc-data-updated', loadData)

    return () => {
      window.removeEventListener('storage', loadData)
      window.removeEventListener('dhmc-data-updated', loadData)
    }
  }, [])

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
              <GitBranch size={48} strokeWidth={1.5} />
            </div>
            <h2>No Chain Data Available</h2>
            <p>
              Run a simulation first to generate Merkle chain data.
              The explorer will visualize the full cryptographic chain structure.
            </p>
            <Link to="/simulator" className="explorer__btn-primary">
              <Play size={16} />
              Go to Simulator
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const moduleEntries = chainData?.modules
    ? Object.entries(chainData.modules).map(([id, mod]) => ({
        id,
        name: id === 'M1' ? 'Intent Parsing' : id === 'M2' ? 'Multi-Source Evaluation' : 'Synthesis & Decision',
        stepCount: mod.stepCount,
        mmrPeak: mod.mmrPeak,
        moduleHash: mod.moduleHash,
      }))
    : []

  const casEntries = casStore
    ? casStore.map(entry => ({
        uri: entry.uri,
        payload: JSON.stringify(entry.payload, null, 2),
        valid: !entry.payload?._tampered,
      }))
    : []

  const abbreviateHash = (hash) => {
    if (!hash) return '—'
    if (hash.length <= 16) return hash
    return `${hash.slice(0, 8)}…${hash.slice(-6)}`
  }

  return (
    <div className="explorer page">
      <div className="container">
        <div className="explorer__header">
          <div className="explorer__header-title">
            <GitBranch className="explorer__header-icon" size={28} />
            <h1>Merkle Chain Explorer</h1>
          </div>
          <p>Visualize and inspect the cryptographic chain structure from the most recent execution.</p>
        </div>

        {/* Split Panel: Tree + Detail */}
        <div className="explorer__panels">
          <div className="explorer__tree-panel">
            <div className="explorer__panel-title">
              <Layers size={16} />
              Merkle Tree
            </div>
            <MerkleTree
              steps={merkleSteps}
              onLeafClick={(node) => setSelectedNode(node)}
            />
          </div>

          <div className="explorer__detail-panel">
            <div className="explorer__panel-title">
              <FileText size={16} />
              Node Details
            </div>

            {!selectedNode ? (
              <div className="explorer__detail-empty">
                <MousePointerClick size={48} strokeWidth={1.5} />
                <p>Select a leaf node in the tree to<br />inspect its cryptographic forensic data</p>
              </div>
            ) : (
              <div className="explorer__detail-content fade-in-up">
                <div className="explorer__detail-header">
                  <div className="explorer__detail-name">
                    {selectedNode.stepId || selectedNode.nodeId || 'Internal Node'}
                  </div>
                  {selectedNode.moduleId && (
                    <span className="explorer__detail-badge">
                      {selectedNode.moduleId}
                    </span>
                  )}
                </div>

                <div className="explorer__detail-cards">
                  {selectedNode.stepType && (
                    <div className="explorer__detail-card">
                      <div className="explorer__card-label"><Box size={14}/> Type</div>
                      <div className="explorer__card-value highlight">{selectedNode.stepType}</div>
                    </div>
                  )}

                  {selectedNode.nonce && (
                    <div className="explorer__detail-card">
                      <div className="explorer__card-label"><Key size={14}/> Nonce</div>
                      <div className="explorer__card-value mono">{selectedNode.nonce}</div>
                    </div>
                  )}

                  {selectedNode.preHash && (
                    <div className="explorer__detail-card">
                      <div className="explorer__card-label"><Hash size={14}/> Pre-Hash</div>
                      <div className="explorer__card-value mono">{selectedNode.preHash}</div>
                    </div>
                  )}

                  {selectedNode.postHash && (
                    <div className="explorer__detail-card">
                      <div className="explorer__card-label"><Hash size={14}/> Post-Hash</div>
                      <div className="explorer__card-value mono">{selectedNode.postHash}</div>
                    </div>
                  )}

                  {selectedNode.binding && (
                    <div className="explorer__detail-card full-width primary">
                      <div className="explorer__card-label"><Link2 size={14}/> Binding Hash</div>
                      <div className="explorer__card-value mono">{selectedNode.binding}</div>
                    </div>
                  )}

                  {selectedNode.inputCasUri && (
                    <div className="explorer__detail-card full-width">
                      <div className="explorer__card-label"><Database size={14}/> Input CAS URI</div>
                      <div className="explorer__card-value mono">{selectedNode.inputCasUri}</div>
                    </div>
                  )}

                  {selectedNode.outputCasUri && (
                    <div className="explorer__detail-card full-width">
                      <div className="explorer__card-label"><Database size={14}/> Output CAS URI</div>
                      <div className="explorer__card-value mono">{selectedNode.outputCasUri}</div>
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
            <h2 className="explorer__section-heading">
              <LinkIcon size={24} className="icon-blue" />
              Chain Timeline
            </h2>

            <div className="explorer__timeline">
              {moduleEntries.map((mod, i) => (
                <div key={mod.id} className="explorer__timeline-item">
                  <div className="explorer__timeline-card">
                    <div className="explorer__timeline-id">{mod.id}</div>
                    <div className="explorer__timeline-name">{mod.name}</div>
                    
                    <div className="explorer__timeline-stats">
                      <div className="explorer__t-stat">
                        <span className="explorer__t-label">Steps</span>
                        <span className="explorer__t-value highlight">{mod.stepCount}</span>
                      </div>
                      {mod.moduleHash && (
                        <div className="explorer__t-stat">
                          <span className="explorer__t-label">Module Hash</span>
                          <span className="explorer__t-value mono">{abbreviateHash(mod.moduleHash)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  {i < moduleEntries.length - 1 && (
                    <div className="explorer__timeline-connector" />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CAS Browser */}
        {casEntries.length > 0 && (
          <div className="explorer__section">
            <h2 className="explorer__section-heading">
              <Database size={24} className="icon-cyan" />
              Content Addressable Storage (CAS)
            </h2>

            <div className="explorer__cas-grid">
              {casEntries.map((entry, i) => (
                <div key={i} className={`explorer__cas-card ${entry.valid ? 'valid' : 'tampered'}`}>
                  <div className="explorer__cas-header">
                    <div className="explorer__cas-uri mono">
                      <Link2 size={14}/>
                      {entry.uri}
                    </div>
                    <div className={`explorer__cas-badge ${entry.valid ? 'valid' : 'tampered'}`}>
                      {entry.valid ? (
                        <><ShieldCheck size={14} /> Valid</>
                      ) : (
                        <><ShieldX size={14} /> Tampered</>
                      )}
                    </div>
                  </div>
                  <div className="explorer__cas-body">
                    <pre className="explorer__cas-code">
                      {entry.payload}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
