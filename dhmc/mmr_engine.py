"""
dhmc/mmr_engine.py
Merkle Mountain Range with epoch checkpointing.
O(log N) amortized append; O(log E) within-epoch audit.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .crypto import _blake3


@dataclass
class MMRNode:
    hash: bytes
    height: int
    index: int
    left_idx: Optional[int] = None
    right_idx: Optional[int] = None
    parent_idx: Optional[int] = None


@dataclass
class EpochCheckpoint:
    epoch_index: int
    mmr_root: bytes
    leaf_count: int
    prev_checkpoint_hash: bytes

    def to_hash(self) -> bytes:
        payload = json.dumps({
            "epoch": self.epoch_index,
            "root": self.mmr_root.hex(),
            "leaves": self.leaf_count,
            "prev": self.prev_checkpoint_hash.hex(),
        }, sort_keys=True).encode()
        return _blake3(payload)


class MerkleMountainRange:
    """
    Append-only MMR with epoch checkpointing.
    Peaks list: one peak per complete binary subtree, tallest first.
    """

    def __init__(self, epoch_size: int = 50):
        self.nodes: List[MMRNode] = []
        self.peaks: List[int] = []  # Indices into self.nodes
        self.leaves: List[int] = [] # Indices into self.nodes
        self.leaf_count: int = 0
        self.epoch_size: int = epoch_size
        self.epoch_index: int = 0
        self.checkpoints: List[EpochCheckpoint] = []
        self._prev_checkpoint_hash: bytes = b'\x00' * 32

    def append(self, leaf_hash: bytes) -> bytes:
        """Insert leaf. Returns current MMR root. O(log N) amortized."""
        idx = len(self.nodes)
        new_node = MMRNode(hash=leaf_hash, height=0, index=idx)
        self.nodes.append(new_node)
        self.peaks.append(idx)
        self.leaves.append(idx)
        self.leaf_count += 1

        # Merge adjacent peaks of equal height (standard MMR operation)
        while len(self.peaks) >= 2 and self.nodes[self.peaks[-2]].height == self.nodes[self.peaks[-1]].height:
            right_idx = self.peaks.pop()
            left_idx = self.peaks.pop()
            merged_hash = _blake3(self.nodes[left_idx].hash, self.nodes[right_idx].hash)
            
            new_idx = len(self.nodes)
            merged_node = MMRNode(
                hash=merged_hash,
                height=self.nodes[left_idx].height + 1,
                index=new_idx,
                left_idx=left_idx,
                right_idx=right_idx
            )
            self.nodes.append(merged_node)
            self.peaks.append(new_idx)
            
            self.nodes[left_idx].parent_idx = new_idx
            self.nodes[right_idx].parent_idx = new_idx

        # Epoch checkpoint if boundary reached
        if self.leaf_count % self.epoch_size == 0:
            self._close_epoch()

        return self.root()

    def root(self) -> bytes:
        """Current MMR root = hash of all peak hashes concatenated."""
        if not self.peaks:
            return b'\x00' * 32
        combined = b''.join(self.nodes[p].hash for p in self.peaks)
        return _blake3(combined)

    def _close_epoch(self):
        cp = EpochCheckpoint(
            epoch_index=self.epoch_index,
            mmr_root=self.root(),
            leaf_count=self.leaf_count,
            prev_checkpoint_hash=self._prev_checkpoint_hash,
        )
        self._prev_checkpoint_hash = cp.to_hash()
        self.checkpoints.append(cp)
        self.epoch_index += 1

    def inclusion_proof(self, leaf_index: int) -> Optional[List[bytes]]:
        """
        Generate inclusion proof for leaf at given index.
        Returns list of sibling hashes for auditor verification, plus other peaks.
        """
        if leaf_index < 0 or leaf_index >= self.leaf_count:
            return None
            
        path = []
        curr_idx = self.leaves[leaf_index]
        
        # Walk up to peak
        while self.nodes[curr_idx].parent_idx is not None:
            parent_idx = self.nodes[curr_idx].parent_idx
            parent_node = self.nodes[parent_idx]
            if parent_node.left_idx == curr_idx:
                path.append(self.nodes[parent_node.right_idx].hash)
            else:
                path.append(self.nodes[parent_node.left_idx].hash)
            curr_idx = parent_idx
            
        # Append other peaks to complete the proof
        peak_hashes = [self.nodes[p].hash for p in self.peaks if p != curr_idx]
        path.extend(peak_hashes)
        
        return path

    def final_commitment(self) -> bytes:
        """
        Module closure: return final checkpoint hash if epochs exist,
        else return raw MMR root.
        """
        if self.checkpoints:
            return self.checkpoints[-1].to_hash()
        return self.root()

    def state_snapshot(self) -> dict:
        return {
            "leaf_count": self.leaf_count,
            "peak_count": len(self.peaks),
            "epoch_index": self.epoch_index,
            "root": self.root().hex(),
            "checkpoint_count": len(self.checkpoints),
        }
