"""
Orama Python Client

A server-side Python client for Orama, a search engine, vector database, and LLM inference provider.
Designed for use in server environments, Python applications, and backend services.

This client does not include browser-specific functionality and is optimized for server-side usage.
"""

from .manager import OramaCoreManager
from .collection import CollectionManager, Index
from .cloud import OramaCloud
from .stream_manager import OramaCoreStream
from .types import *
from .utils import create_random_string
from .profile import Profile

__version__ = "1.2.0"
__all__ = [
    "OramaCoreManager",
    "CollectionManager", 
    "OramaCloud",
    "OramaCoreStream",
    "Index",
    "Profile",
    "create_random_string"
]

def dedupe():
    """Create a deduplication function similar to the TypeScript version."""
    seen_messages = set()
    
    def _dedupe(message=None):
        if not message:
            return ""
        
        if message in seen_messages:
            return ""
        
        seen_messages.add(message)
        return message
    
    return _dedupe