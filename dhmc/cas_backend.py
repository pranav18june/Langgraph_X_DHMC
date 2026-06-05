import abc
from typing import Any, Optional, Tuple
from collections import OrderedDict

class CASBackend(abc.ABC):
    """Abstract interface for Content-Addressable Storage (CAS) backends."""
    
    @abc.abstractmethod
    def put(self, uri: str, payload: Any) -> Optional[Tuple[str, Any]]:
        """
        Store a payload.
        
        Returns:
            Optional[Tuple[str, Any]]: (evicted_uri, evicted_payload) if an eviction occurred, else None.
        """
        pass
        
    @abc.abstractmethod
    def get(self, uri: str) -> Optional[Any]:
        """
        Retrieve a payload by URI.
        
        Returns:
            Optional[Any]: The payload if found, else None.
        """
        pass
        
    @abc.abstractmethod
    def contains(self, uri: str) -> bool:
        """Check if a URI exists in the store."""
        pass


class InMemoryCASBackend(CASBackend):
    """In-memory CAS backend with LRU eviction."""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.store: OrderedDict[str, Any] = OrderedDict()
        
    def put(self, uri: str, payload: Any) -> Optional[Tuple[str, Any]]:
        self.store[uri] = payload
        if len(self.store) > self.max_entries:
            return self.store.popitem(last=False)
        return None
        
    def get(self, uri: str) -> Optional[Any]:
        return self.store.get(uri)
        
    def contains(self, uri: str) -> bool:
        return uri in self.store
