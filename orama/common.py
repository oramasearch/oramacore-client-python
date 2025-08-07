"""
Common client functionality for Orama Python client.
"""

import json
import asyncio
from typing import Dict, Any, Optional, Union, Literal
from dataclasses import dataclass
import aiohttp
from urllib.parse import urlencode, urljoin

from .utils import safe_json_parse

ApiKeyPosition = Literal["header", "query-params"]

@dataclass
class JWTRequestResponse:
    jwt: str
    writer_url: str
    reader_api_key: str
    reader_url: str
    expires_in: int

@dataclass
class ApiKeyAuth:
    type: Literal["apiKey"] = "apiKey"
    api_key: str = ""
    reader_url: Optional[str] = None
    writer_url: Optional[str] = None

@dataclass 
class JwtAuth:
    type: Literal["jwt"] = "jwt"
    auth_jwt_url: str = ""
    collection_id: str = ""
    private_api_key: str = ""
    reader_url: Optional[str] = None
    writer_url: Optional[str] = None

AuthConfig = Union[ApiKeyAuth, JwtAuth]

class Auth:
    """Authentication handler for Orama client."""
    
    def __init__(self, config: AuthConfig):
        self.config = config
    
    async def get_ref(
        self, 
        target: Literal["reader", "writer"], 
        session: Optional[aiohttp.ClientSession] = None
    ) -> Dict[str, str]:
        """Get authentication reference for the target."""
        if self.config.type == "apiKey":
            bearer = self.config.api_key
            if target == "writer" and not self.config.writer_url:
                raise ValueError(
                    "Cannot perform a request to a writer without the writerURL. "
                    "Use `cluster.writerURL` to configure it"
                )
            if target == "reader" and not self.config.reader_url:
                raise ValueError(
                    "Cannot perform a request to a reader without the readerURL. "
                    "Use `cluster.readerURL` to configure it"
                )
            base_url = self.config.writer_url if target == "writer" else self.config.reader_url
        
        elif self.config.type == "jwt":
            jwt_response = await self._get_jwt_token(
                self.config.auth_jwt_url,
                self.config.collection_id,
                self.config.private_api_key,
                "write",
                session
            )
            
            if target == "reader":
                base_url = self.config.reader_url or jwt_response.reader_url
                bearer = jwt_response.reader_api_key
            else:
                bearer = jwt_response.jwt
                base_url = self.config.writer_url or jwt_response.writer_url
        
        return {
            "bearer": bearer,
            "base_url": base_url
        }
    
    async def _get_jwt_token(
        self,
        auth_jwt_url: str,
        collection_id: str,
        private_api_key: str,
        scope: str,
        session: Optional[aiohttp.ClientSession] = None
    ) -> JWTRequestResponse:
        """Get JWT token from authentication endpoint."""
        payload = {
            "collectionId": collection_id,
            "privateApiKey": private_api_key,
            "scope": scope
        }
        
        close_session = session is None
        if session is None:
            session = aiohttp.ClientSession()
        
        try:
            async with session.post(
                auth_jwt_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if not response.ok:
                    text = await response.text()
                    raise Exception(
                        f"JWT request to {auth_jwt_url} failed with status {response.status}: {text}"
                    )
                
                data = await response.json()
                return JWTRequestResponse(
                    jwt=data["jwt"],
                    writer_url=data["writerURL"],
                    reader_api_key=data["readerApiKey"],
                    reader_url=data["readerURL"],
                    expires_in=data["expiresIn"]
                )
        finally:
            if close_session:
                await session.close()

@dataclass
class ClientRequest:
    target: Literal["reader", "writer"]
    method: Literal["GET", "POST"]
    path: str
    api_key_position: ApiKeyPosition
    body: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, str]] = None

@dataclass
class ClientConfig:
    auth: Auth

class Client:
    """HTTP client for Orama API."""
    
    def __init__(self, config: ClientConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def request(self, req: ClientRequest) -> Any:
        """Make an HTTP request and return JSON response."""
        response = await self.get_response(req)
        
        if not (200 <= response.status < 300):
            try:
                text = await response.text()
            except Exception as e:
                text = f"Unable to get response body {e}"
            
            params_str = urlencode(req.params or {})
            raise Exception(
                f'Request to "{req.path}?{params_str}" failed with status {response.status}: {text}'
            )
        
        return await response.json()
    
    async def get_response(self, req: ClientRequest) -> aiohttp.ClientResponse:
        """Get HTTP response for a request."""
        auth_ref = await self.config.auth.get_ref(req.target)
        base_url = auth_ref["base_url"]
        bearer = auth_ref["bearer"]
        
        url = urljoin(base_url, req.path)
        headers = {"Content-Type": "application/json"}
        
        if req.api_key_position == "header":
            headers["Authorization"] = f"Bearer {bearer}"
        
        params = req.params or {}
        if req.api_key_position == "query-params":
            params["api-key"] = bearer
        
        session = await self._get_session()
        
        kwargs = {
            "url": url,
            "method": req.method,
            "headers": headers,
            "params": params if params else None
        }
        
        if req.body and req.method == "POST":
            kwargs["json"] = req.body
        
        response = await session.request(**kwargs)
        
        if response.status == 401:
            raise Exception("Unauthorized: are you using the correct Api Key?")
        
        if response.status == 400:
            error_text = await response.text()
            raise Exception(f"Bad Request: {error_text} (path: {url})")
        
        return response