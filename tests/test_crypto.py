import pytest
from dhmc.crypto import _blake3, _canonical_bytes

def test_blake3():
    hash1 = _blake3(b"hello")
    hash2 = _blake3(b"world")
    hash3 = _blake3(b"hello")
    assert hash1 != hash2
    assert hash1 == hash3
    assert len(hash1) == 32

def test_blake3_multiple_parts():
    hash_combined = _blake3(b"hello", b"world")
    hash_single = _blake3(b"helloworld")
    assert hash_combined == hash_single

def test_canonical_bytes():
    dict1 = {"b": 2, "a": 1}
    dict2 = {"a": 1, "b": 2}
    assert _canonical_bytes(dict1) == _canonical_bytes(dict2)
    assert b"a" in _canonical_bytes(dict1)

def test_canonical_bytes_deterministic_extensions():
    import datetime
    from decimal import Decimal

    # Test datetime and date
    dt = datetime.datetime(2026, 6, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)
    d = datetime.date(2026, 6, 4)
    assert _canonical_bytes(dt) == b'"2026-06-04T12:00:00+00:00"'
    assert _canonical_bytes(d) == b'"2026-06-04"'

    # Test decimal
    dec = Decimal("123.45")
    assert _canonical_bytes(dec) == b'"123.45"'

    # Test custom decimal (class named Decimal or ending with Decimal)
    class CustomDecimal:
        def __init__(self, val: str):
            self.val = val
        def __str__(self):
            return self.val
    
    cd = CustomDecimal("99.99")
    assert _canonical_bytes(cd) == b'"99.99"'

    # Test bytes and bytearray
    b_val = b"hello"
    ba_val = bytearray(b"world")
    assert _canonical_bytes(b_val) == b'"68656c6c6f"'
    assert _canonical_bytes(ba_val) == b'"776f726c64"'

    # Test nested dict/list/tuple structure
    nested = {
        "bytes": b_val,
        "decimal": dec,
        "date": d,
        "list": [dt, cd]
    }
    expected = b'{"bytes": "68656c6c6f", "date": "2026-06-04", "decimal": "123.45", "list": ["2026-06-04T12:00:00+00:00", "99.99"]}'
    assert _canonical_bytes(nested) == expected

def test_canonical_bytes_type_error():
    # Unsupported types should raise TypeError
    with pytest.raises(TypeError):
        _canonical_bytes({1, 2, 3})  # set is unsupported
    
    class UnserializableClass:
        pass
    
    with pytest.raises(TypeError):
        _canonical_bytes(UnserializableClass())
        
    with pytest.raises(TypeError):
        _canonical_bytes({"key": UnserializableClass()})

