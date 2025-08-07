"""
Profile management for Orama Python client (server-side only).
"""

import uuid
import json
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urlparse

class Profile:
    """User profile management class for server-side usage."""
    
    def __init__(self, endpoint: str, api_key: str):
        if not endpoint or not api_key:
            raise ValueError("Endpoint and API Key are required to create a Profile")
        
        if not isinstance(endpoint, str) or not isinstance(api_key, str):
            raise ValueError("Endpoint and API Key must be strings")
        
        self.endpoint = endpoint
        self.api_key = api_key
        self.identity: Optional[str] = None
        self.user_alias: Optional[str] = None
        self.params: Optional[Dict[str, str]] = None
        
        # Generate user ID for server-side session
        self.user_id = str(uuid.uuid4())
    
    def set_params(self, identify_url: str, index: str) -> None:
        """Set profile parameters."""
        parsed_url = urlparse(identify_url)
        telemetry_domain = f"{parsed_url.scheme}://{parsed_url.netloc}/identify"
        
        self.params = {
            "identify_url": telemetry_domain,
            "index": index
        }
    
    def get_identity(self) -> Optional[str]:
        """Get user identity."""
        return self.identity
    
    def get_user_id(self) -> str:
        """Get user ID."""
        return self.user_id
    
    def get_alias(self) -> Optional[str]:
        """Get user alias."""
        return self.user_alias
    
    async def _send_profile_data(self, data: Dict[str, Any]) -> None:
        """Send profile data to telemetry endpoint."""
        if not self.params:
            raise ValueError("Orama Profile is not initialized")
        
        body = {
            **data,
            "visitorId": self.get_user_id(),
            "index": self.params["index"]
        }
        
        endpoint = f"{self.params['identify_url']}?api-key={self.api_key}"
        
        # Use aiohttp for HTTP requests instead of browser-specific sendBeacon
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=body,
                headers={"Content-Type": "application/json"}
            ) as response:
                if not response.ok:
                    raise ValueError(f"Failed to send profile data: {response.status}")
    
    async def identify(self, identity: str) -> None:
        """Set user identity."""
        if not isinstance(identity, str):
            raise ValueError("Identity must be a string")
        
        await self._send_profile_data({
            "entity": "identity",
            "id": identity
        })
        
        self.identity = identity
    
    async def alias(self, alias: str) -> None:
        """Set user alias."""
        if not isinstance(alias, str):
            raise ValueError("Alias must be a string")
        
        await self._send_profile_data({
            "entity": "alias", 
            "id": alias
        })
        
        self.user_alias = alias
    
    def reset(self) -> None:
        """Reset user profile."""
        self.user_id = str(uuid.uuid4())
        self.identity = None
        self.user_alias = None