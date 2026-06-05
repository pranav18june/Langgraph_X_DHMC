import pytest
from dhmc.mmr_engine import MerkleMountainRange
from dhmc.crypto import _blake3

def test_mmr_append():
    mmr = MerkleMountainRange(epoch_size=10)
    root1 = mmr.append(b"leaf1")
    root2 = mmr.append(b"leaf2")
    assert root1 != root2
    assert mmr.leaf_count == 2
    assert len(mmr.peaks) == 1  # 2 leaves merge into 1 peak
    
    root3 = mmr.append(b"leaf3")
    assert mmr.leaf_count == 3
    assert len(mmr.peaks) == 2  # height 1 peak, and height 0 peak

def test_mmr_inclusion_proof():
    mmr = MerkleMountainRange()
    for i in range(5):
        mmr.append(_blake3(i.to_bytes(4, 'big')))
        
    proof = mmr.inclusion_proof(2)
    assert proof is not None
    assert len(proof) > 0
    
    # Proof for an invalid index should return None
    invalid_proof = mmr.inclusion_proof(10)
    assert invalid_proof is None

def test_mmr_epoch_checkpoint():
    mmr = MerkleMountainRange(epoch_size=3)
    for i in range(3):
        mmr.append(_blake3(i.to_bytes(4, 'big')))
        
    assert mmr.epoch_index == 1
    assert len(mmr.checkpoints) == 1
    
    mmr.append(_blake3(b"leaf4"))
    assert mmr.epoch_index == 1
