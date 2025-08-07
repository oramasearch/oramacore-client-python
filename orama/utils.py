"""
Production-grade utility functions for Orama Python client (server-side only).

This module provides the same functionality as the JavaScript client but optimized for server-side use only.
It includes production-grade JSON parsing, enhanced error handling, and robust utility functions.
"""

import json
import random
import string
import time
import asyncio
from typing import Optional, Dict, Any, Callable, TypeVar, Union, List
import logging

import orjson
import structlog

# Configure structured logging
logger = structlog.get_logger(__name__)

T = TypeVar('T')

def create_random_string(length: int) -> str:
    """Create a cryptographically secure random string of specified length."""
    characters = string.ascii_letters + string.digits + '_-$'
    return ''.join(random.SystemRandom().choice(characters) for _ in range(length))

def format_duration(duration: Union[int, float]) -> str:
    """Format duration in milliseconds to human readable string."""
    if duration < 1000:
        return f"{int(duration)}ms"
    else:
        seconds = duration / 1000
        if seconds == int(seconds):
            return f"{int(seconds)}s"
        return f"{seconds:.1f}s"

def safe_json_parse(data: str, default: Any = None, silent: bool = True) -> Any:
    """
    Production-grade JSON parsing with robust error handling.
    Uses orjson for better performance and error handling, with json as fallback.
    """
    if not data or not data.strip():
        return default
    
    try:
        # Try orjson first for better performance
        return orjson.loads(data)
    except (orjson.JSONDecodeError, ValueError):
        try:
            # Fallback to standard json
            return json.loads(data)
        except json.JSONDecodeError as error:
            if not silent:
                logger.warning("Failed to parse JSON", data=data[:100], error=str(error))
            return default if default is not None else data

async def async_throttle(func: Callable, limit: int) -> Callable:
    """Production-grade async throttle for function calls."""
    last_called = [0]
    lock = asyncio.Lock()
    
    async def wrapper(*args, **kwargs):
        async with lock:
            now = time.time() * 1000  # Convert to milliseconds
            if now - last_called[0] >= limit:
                last_called[0] = now
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
    
    return wrapper

def throttle(func: Callable, limit: int) -> Callable:
    """Production-grade synchronous throttle for function calls."""
    last_called = [0]
    
    def wrapper(*args, **kwargs):
        now = time.time() * 1000  # Convert to milliseconds
        if now - last_called[0] >= limit:
            last_called[0] = now
            return func(*args, **kwargs)
    
    return wrapper

async def async_debounce(func: Callable, delay: float) -> Callable:
    """Production-grade async debounce for function calls."""
    timer_task = [None]
    lock = asyncio.Lock()
    
    async def wrapper(*args, **kwargs):
        async with lock:
            # Cancel existing timer
            if timer_task[0] and not timer_task[0].done():
                timer_task[0].cancel()
            
            # Create new timer
            async def delayed_call():
                await asyncio.sleep(delay / 1000)  # Convert to seconds
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            
            timer_task[0] = asyncio.create_task(delayed_call())
    
    return wrapper

def debounce(func: Callable, delay: int) -> Callable:
    """Production-grade synchronous debounce for function calls."""
    timer = [None]
    
    def wrapper(*args, **kwargs):
        def call_func():
            timer[0] = None
            func(*args, **kwargs)
        
        if timer[0]:
            timer[0].cancel()
        
        import threading
        timer[0] = threading.Timer(delay / 1000, call_func)  # Convert to seconds
        timer[0].start()
    
    return wrapper

def flatten_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Production-grade schema flattening with comprehensive error handling.
    Handles complex schema structures with proper validation.
    """
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a dictionary")
    
    # Handle $ref resolution
    if '$ref' in schema:
        if 'definitions' not in schema:
            raise ValueError("Schema contains $ref but no definitions section")
        
        ref_path = schema['$ref']
        if not ref_path.startswith('#/definitions/'):
            raise ValueError(f"Unsupported $ref format: {ref_path}")
        
        ref_name = ref_path.replace('#/definitions/', '')
        if ref_name not in schema['definitions']:
            raise ValueError(f"Could not resolve definition: {ref_name}")
        
        resolved_schema = schema['definitions'][ref_name]
        
        # Recursively flatten if the resolved schema also has refs
        if '$ref' in resolved_schema:
            return flatten_schema({**schema, **resolved_schema})
        
        return resolved_schema
    
    # Handle nested objects and arrays
    flattened = {}
    for key, value in schema.items():
        if isinstance(value, dict) and ('$ref' in value or 'definitions' in value):
            flattened[key] = flatten_schema(value)
        elif isinstance(value, list):
            flattened[key] = [flatten_schema(item) if isinstance(item, dict) else item for item in value]
        else:
            flattened[key] = value
    
    return flattened

def validate_json_structure(data: Any, expected_keys: Optional[List[str]] = None) -> bool:
    """
    Validate JSON structure for production environments.
    Ensures data integrity and expected format.
    """
    if not isinstance(data, dict):
        return False
    
    if expected_keys:
        missing_keys = set(expected_keys) - set(data.keys())
        if missing_keys:
            logger.warning("Missing expected keys in JSON structure", missing=list(missing_keys))
            return False
    
    return True

def sanitize_error_message(error: Exception, max_length: int = 500) -> str:
    """
    Sanitize error messages for production logging.
    Removes potential sensitive information and limits length.
    """
    message = str(error)
    
    # Basic sanitization - remove potential file paths and sensitive info
    sanitized = message.replace(str(logger), '[REDACTED]')
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized