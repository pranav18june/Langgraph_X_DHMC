import datetime
import decimal
import json
from typing import Any
import blake3

def _blake3(*parts: bytes) -> bytes:
    h = blake3.blake3()
    for p in parts:
        h.update(p)
    return h.digest()

def _to_canonical_json_compatible(obj: Any) -> Any:
    """Recursively convert objects to deterministic JSON-serializable primitives."""
    if isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if isinstance(k, str):
                key_str = k
            elif isinstance(k, (int, float, bool)) or k is None:
                key_str = str(k)
            elif isinstance(k, datetime.datetime):
                key_str = k.isoformat()
            elif isinstance(k, datetime.date):
                key_str = k.isoformat()
            elif isinstance(k, decimal.Decimal) or type(k).__name__ == "Decimal" or type(k).__name__.endswith("Decimal"):
                key_str = str(k)
            elif isinstance(k, (bytes, bytearray)):
                key_str = k.hex()
            else:
                raise TypeError(f"Dict key type {type(k)} is not serializable in `_canonical_bytes`")
            res[key_str] = _to_canonical_json_compatible(v)
        return res
    elif isinstance(obj, (list, tuple)):
        return [_to_canonical_json_compatible(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal) or type(obj).__name__ == "Decimal" or type(obj).__name__.endswith("Decimal"):
        return str(obj)
    elif isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    else:
        raise TypeError(f"Type {type(obj)} is not serializable in `_canonical_bytes`")

def _canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON serialization for payload hashing."""
    serializable_obj = _to_canonical_json_compatible(obj)
    return json.dumps(serializable_obj, sort_keys=True).encode()

