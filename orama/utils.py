"""
Utility functions for Orama Python client (server-side only).
"""

import json
import random
import string
import time
from typing import Optional, Dict, Any, Callable, TypeVar

T = TypeVar('T')

def create_random_string(length: int) -> str:
    """Create a random string of specified length."""
    characters = string.ascii_letters + string.digits + '_-$'
    return ''.join(random.choice(characters) for _ in range(length))

def format_duration(duration: int) -> str:
    """Format duration in milliseconds to human readable string."""
    if duration < 1000:
        return f"{duration}ms"
    else:
        seconds = duration / 1000
        if seconds.is_integer():
            return f"{int(seconds)}s"
        return f"{seconds:.1f}s"

def safe_json_parse(data: str, silent: bool = True) -> Any:
    """Safely parse JSON with fallback."""
    try:
        return json.loads(data)
    except json.JSONDecodeError as error:
        if not silent:
            print(f"Recovered from failed JSON parsing with error: {error}")
        return data

def throttle(func: Callable, limit: int) -> Callable:
    """Throttle function calls."""
    last_called = [0]
    
    def wrapper(*args, **kwargs):
        now = time.time() * 1000  # Convert to milliseconds
        if now - last_called[0] >= limit:
            last_called[0] = now
            return func(*args, **kwargs)
    
    return wrapper

def debounce(func: Callable, delay: int) -> Callable:
    """Debounce function calls."""
    timer = [None]
    
    def wrapper(*args, **kwargs):
        def call_func():
            timer[0] = None
            func(*args, **kwargs)
        
        if timer[0]:
            timer[0].cancel()
        
        import threading
        timer[0] = threading.Timer(delay / 1000, call_func)
        timer[0].start()
    
    return wrapper

def flatten_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a JSON schema (Python equivalent of flattenZodSchema).
    This is a simplified version that handles basic schema structures.
    """
    if '$ref' in schema and 'definitions' in schema:
        ref_name = schema['$ref'].replace('#/definitions/', '')
        if ref_name in schema['definitions']:
            return schema['definitions'][ref_name]
        else:
            raise ValueError(f"Could not resolve definition: {ref_name}")
    
    return schema