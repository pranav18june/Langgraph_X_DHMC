import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import { Crown } from 'lucide-react';
import './MerkleTree.css';

function pseudoHash(a, b) {
  const combined = a + b;
  let h = 0;
  for (let i = 0; i < combined.length; i++) {
    h = ((h << 5) - h + combined.charCodeAt(i)) | 0;
  }
  const hex = Math.abs(h).toString(16).padStart(8, '0');
  return hex + hex.split('').reverse().join('');
}

function abbreviateHash(hash) {
  if (!hash) return '???';
  if (hash.length <= 8) return hash;
  return hash.slice(0, 4) + '…' + hash.slice(-4);
}

function buildMerkleTree(leaves) {
  if (!leaves || leaves.length === 0) return { levels: [], peaks: [] };

  const levels = [];
  let currentLevel = leaves.map((leaf, i) => ({
    id: `l0_i${i}`,
    hash: leaf.bindingHash || leaf.binding || `leaf_${i}`,
    isLeaf: true,
    leafIndex: i,
    moduleId: leaf.moduleId,
    nodeName: leaf.nodeName || leaf.nodeId,
    children: []
  }));
  levels.push(currentLevel);

  const peaks = [];
  let l = 1;

  while (currentLevel.length > 1) {
    const nextLevel = [];
    for (let i = 0; i < currentLevel.length; i += 2) {
      if (i + 1 < currentLevel.length) {
        nextLevel.push({
          id: `l${l}_i${nextLevel.length}`,
          hash: pseudoHash(currentLevel[i].hash, currentLevel[i + 1].hash),
          isLeaf: false,
          leafIndex: null,
          moduleId: null,
          nodeName: null,
          children: [currentLevel[i].id, currentLevel[i + 1].id]
        });
      } else {
        // Peak that couldn't be paired
        peaks.push({ level: levels.length - 1, index: i, id: currentLevel[i].id });
        nextLevel.push({
          ...currentLevel[i],
          id: `l${l}_i${nextLevel.length}`,
          isLeaf: false,
          children: [currentLevel[i].id] // Single carry-over line
        });
      }
    }
    levels.push(nextLevel);
    currentLevel = nextLevel;
    l++;
  }

  if (currentLevel.length === 1) {
    peaks.push({ level: levels.length - 1, index: 0, id: currentLevel[0].id });
  }

  return { levels, peaks };
}

function getModuleClass(moduleId) {
  if (!moduleId) return '';
  const m = moduleId.toUpperCase();
  if (m === 'M1') return 'module-m1';
  if (m === 'M2') return 'module-m2';
  if (m === 'M3') return 'module-m3';
  return '';
}

function MerkleTreeNode({ node, isPeakNode, isSelected, onClick, isDimmed }) {
  const classes = [
    'merkle-node',
    node.isLeaf ? getModuleClass(node.moduleId) : 'internal',
    isPeakNode ? 'peak' : '',
    isSelected ? 'selected' : '',
    isDimmed ? 'dimmed' : ''
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} id={node.id} onClick={() => onClick && onClick(node)}>
      {isPeakNode && (
        <span className="peak-icon"><Crown size={14} /></span>
      )}
      <div className="merkle-node-circle">
        <span className="merkle-node-inner">{abbreviateHash(node.hash)}</span>
      </div>
      <span className="merkle-hash">{abbreviateHash(node.hash)}</span>
      {node.isLeaf && node.nodeName && (
        <span className="merkle-leaf-name">{node.nodeName}</span>
      )}
      <span className="merkle-full-hash">{node.hash}</span>
    </div>
  );
}

export default function MerkleTree({ steps = [], onLeafClick }) {
  const [selectedLeaf, setSelectedLeaf] = useState(null);
  const [connections, setConnections] = useState([]);
  const canvasRef = useRef(null);

  const { levels, peaks } = useMemo(() => buildMerkleTree(steps), [steps]);
  const displayLevels = useMemo(() => [...levels].reverse(), [levels]);

  const activePathIds = useMemo(() => {
    if (selectedLeaf === null) return new Set();
    const active = new Set();
    const leafNode = levels[0][selectedLeaf];
    if (!leafNode) return active;
    
    // Trace up the tree
    let currentId = leafNode.id;
    active.add(currentId);
    
    for (let l = 1; l < levels.length; l++) {
      const parent = levels[l].find(n => n.children.includes(currentId));
      if (parent) {
        active.add(parent.id);
        currentId = parent.id;
      } else {
        break;
      }
    }
    return active;
  }, [selectedLeaf, levels]);

  const handleNodeClick = useCallback((node) => {
    if (node.isLeaf) {
      setSelectedLeaf(node.leafIndex);
      if (onLeafClick) onLeafClick(steps[node.leafIndex], node.leafIndex);
    }
  }, [onLeafClick, steps]);

  const drawConnections = useCallback(() => {
    if (!canvasRef.current || levels.length === 0) return;
    const canvasRect = canvasRef.current.getBoundingClientRect();
    const newConns = [];

    levels.forEach(level => {
      level.forEach(node => {
        if (!node.children || node.children.length === 0) return;
        
        const parentEl = document.getElementById(node.id);
        if (!parentEl) return;
        const pRect = parentEl.getBoundingClientRect();
        const pX = pRect.left + pRect.width / 2 - canvasRect.left;
        const pY = pRect.top + pRect.height / 2 - canvasRect.top; // Center of circle

        node.children.forEach(childId => {
          const childEl = document.getElementById(childId);
          if (!childEl) return;
          const cRect = childEl.getBoundingClientRect();
          const cX = cRect.left + cRect.width / 2 - canvasRect.left;
          const cY = cRect.top + cRect.height / 2 - canvasRect.top; // Center of circle

          const isPathActive = activePathIds.has(node.id) && activePathIds.has(childId);
          const isCarryOver = Math.abs(pX - cX) < 5; // Straight vertical line

          const midY = (pY + cY) / 2;
          const d = `M ${pX} ${pY + 20} C ${pX} ${midY}, ${cX} ${midY}, ${cX} ${cY - 20}`;
          
          newConns.push({
            id: `${node.id}-${childId}`,
            d,
            active: isPathActive,
            carryOver: isCarryOver
          });
        });
      });
    });
    setConnections(newConns);
  }, [levels, activePathIds]);

  useEffect(() => {
    // Small timeout to allow DOM to render before measuring
    const timer = setTimeout(drawConnections, 100);
    window.addEventListener('resize', drawConnections);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', drawConnections);
    };
  }, [drawConnections]);

  if (!steps || steps.length === 0) {
    return (
      <div className="merkle-tree">
        <div className="merkle-empty">No steps to build Merkle tree</div>
      </div>
    );
  }

  return (
    <div className="merkle-tree">
      <div className="merkle-header">
        <h3>Merkle Mountain Range</h3>
        <span className="merkle-badge">{steps.length} Leaves</span>
      </div>

      <div className="merkle-canvas" ref={canvasRef}>
        {/* SVG Connections Layer */}
        <svg className="merkle-svg-layer" width="100%" height="100%">
          <defs>
            <linearGradient id="active-line" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2dd4bf" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.8" />
            </linearGradient>
          </defs>
          {connections.map(conn => (
            <path
              key={conn.id}
              d={conn.d}
              className={`merkle-edge ${conn.active ? 'active' : ''} ${conn.carryOver ? 'carry-over' : ''}`}
            />
          ))}
        </svg>

        <div className="merkle-levels">
          {displayLevels.map((level, dIdx) => {
            return (
              <div className="merkle-level" key={`level-${dIdx}`}>
                {level.map((node, nIdx) => {
                  const isDimmed = selectedLeaf !== null && !activePathIds.has(node.id);
                  const isPeakNode = peaks.some(p => p.id === node.id);
                  return (
                    <MerkleTreeNode
                      key={node.id}
                      node={node}
                      isPeakNode={isPeakNode}
                      isSelected={node.isLeaf && node.leafIndex === selectedLeaf}
                      isDimmed={isDimmed}
                      onClick={handleNodeClick}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      <div className="merkle-legend">
        <div className="merkle-legend-item">
          <span className="merkle-legend-dot m1" /> M1 Intent
        </div>
        <div className="merkle-legend-item">
          <span className="merkle-legend-dot m2" /> M2 Evaluation
        </div>
        <div className="merkle-legend-item">
          <span className="merkle-legend-dot m3" /> M3 Decision
        </div>
        <div className="merkle-legend-item">
          <span className="merkle-legend-dot peak" /> Peak Node
        </div>
      </div>
    </div>
  );
}
