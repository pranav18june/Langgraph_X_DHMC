import { useMemo, useState, useCallback } from 'react';
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
    hash: leaf.bindingHash || leaf.binding || `leaf_${i}`,
    isLeaf: true,
    leafIndex: i,
    moduleId: leaf.moduleId,
    nodeName: leaf.nodeName || leaf.nodeId,
  }));
  levels.push(currentLevel);

  const peaks = [];

  while (currentLevel.length > 1) {
    const nextLevel = [];
    for (let i = 0; i < currentLevel.length; i += 2) {
      if (i + 1 < currentLevel.length) {
        nextLevel.push({
          hash: pseudoHash(currentLevel[i].hash, currentLevel[i + 1].hash),
          isLeaf: false,
          leafIndex: null,
          moduleId: null,
          nodeName: null,
        });
      } else {
        peaks.push({ level: levels.length - 1, index: i });
        nextLevel.push({ ...currentLevel[i], isLeaf: false });
      }
    }
    levels.push(nextLevel);
    currentLevel = nextLevel;
  }

  if (currentLevel.length === 1) {
    peaks.push({ level: levels.length - 1, index: 0 });
  }

  return { levels, peaks };
}

function isPeak(peaks, levelIdx, nodeIdx) {
  return peaks.some(p => p.level === levelIdx && p.index === nodeIdx);
}

function getModuleClass(moduleId) {
  if (!moduleId) return '';
  const m = moduleId.toUpperCase();
  if (m === 'M1') return 'module-m1';
  if (m === 'M2') return 'module-m2';
  if (m === 'M3') return 'module-m3';
  return '';
}

function MerkleTreeNode({ node, isPeakNode, isSelected, onClick }) {
  const classes = [
    'merkle-node',
    node.isLeaf ? getModuleClass(node.moduleId) : 'internal',
    isPeakNode ? 'peak' : '',
    isSelected ? 'selected' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} onClick={() => onClick && onClick(node)}>
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

  const { levels, peaks } = useMemo(() => buildMerkleTree(steps), [steps]);
  const displayLevels = useMemo(() => [...levels].reverse(), [levels]);

  const handleNodeClick = useCallback((node) => {
    if (node.isLeaf) {
      setSelectedLeaf(node.leafIndex);
      if (onLeafClick) onLeafClick(steps[node.leafIndex], node.leafIndex);
    }
  }, [onLeafClick, steps]);

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

      <div className="merkle-canvas">
        <div className="merkle-levels">
          {displayLevels.map((level, dIdx) => {
            const origLevelIdx = levels.length - 1 - dIdx;
            return (
              <div className="merkle-level" key={`level-${dIdx}`}>
                {level.map((node, nIdx) => (
                  <MerkleTreeNode
                    key={`${dIdx}-${nIdx}`}
                    node={node}
                    isPeakNode={isPeak(peaks, origLevelIdx, nIdx)}
                    isSelected={node.isLeaf && node.leafIndex === selectedLeaf}
                    onClick={handleNodeClick}
                  />
                ))}
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
