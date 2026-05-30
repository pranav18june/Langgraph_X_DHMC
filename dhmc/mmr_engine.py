"""
dhmc/mmr_engine.py
Merkle Mountain Range with epoch checkpointing.
O(log N) amortized append; O(log E) within-epoch audit.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


def blake3_hash(*parts: bytes) -> bytes:
    """
    BLAKE3 substitute using SHA3-256 (available in stdlib).
    In production: replace with blake3 pip package.
    Input parts are concatenated then hashed.
    """
    h = hashlib.sha3_256()
    for p in parts:
        h.update(p)
    return h.digest()


@dataclass
class MMRPeak:
    height: int
    hash: bytes


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
        return blake3_hash(payload)


class MerkleMountainRange:
    """
    Append-only MMR with epoch checkpointing.
    Peaks list: one peak per complete binary subtree, tallest first.
    """

    def __init__(self, epoch_size: int = 50):
        self.peaks: List[MMRPeak] = []
        self.leaf_count: int = 0
        self.epoch_size: int = epoch_size
        self.epoch_index: int = 0
        self.checkpoints: List[EpochCheckpoint] = []
        self._prev_checkpoint_hash: bytes = b'\x00' * 32

    def append(self, leaf_hash: bytes) -> bytes:
        """Insert leaf. Returns current MMR root. O(log N) amortized."""
        new_peak = MMRPeak(height=0, hash=leaf_hash)
        self.peaks.append(new_peak)
        self.leaf_count += 1

        # Merge adjacent peaks of equal height (standard MMR operation)
        while len(self.peaks) >= 2 and self.peaks[-2].height == self.peaks[-1].height:
            right = self.peaks.pop()
            left = self.peaks.pop()
            merged_hash = blake3_hash(left.hash, right.hash)
            self.peaks.append(MMRPeak(height=left.height + 1, hash=merged_hash))

        # Epoch checkpoint if boundary reached
        if self.leaf_count % self.epoch_size == 0:
            self._close_epoch()

        return self.root()

    def root(self) -> bytes:
        """Current MMR root = hash of all peak hashes concatenated."""
        if not self.peaks:
            return b'\x00' * 32
        combined = b''.join(p.hash for p in self.peaks)
        return blake3_hash(combined)

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
        Returns list of sibling hashes for auditor verification.
        Simplified: full implementation requires leaf-to-peak path tracking.
        """
        # Placeholder — production implementation tracks individual leaves
        # For prototype purposes returns the current peaks as proof context
        return [p.hash for p in self.peaks]

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
