"""
Collection management and search functionality for Orama Python client.
"""

import json
import uuid
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, AsyncGenerator, Literal
from dataclasses import dataclass

import aiohttp
import structlog
from aiohttp_sse_client import sse_client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .common import Auth, Client, ClientConfig, ClientRequest, ApiKeyAuth, JwtAuth
from .types import (
    AnyObject, SearchParams, SearchResult, Hit, Elapsed, Hook, LLMConfig, 
    NLPSearchStreamResult, NLPSearchStreamStatus, ExecuteToolsResult,
    ExecuteToolsParsedResponse, Tool, SystemPrompt, InsertSystemPromptBody,
    InsertToolBody, UpdateToolBody, SystemPromptValidationResponse, UpdateTriggerResponse
)
from .utils import format_duration, create_random_string, safe_json_parse
from .stream_manager import SSEEventParser, safe_json_parse as stream_safe_json_parse
from .profile import Profile
from .stream_manager import OramaCoreStream, CreateAISessionConfig

DEFAULT_READER_URL = "https://collections.orama.com"
DEFAULT_JWT_URL = "https://app.orama.com/api/user/jwt"

# Configure structured logging
logger = structlog.get_logger(__name__)

@dataclass
class CollectionManagerConfig:
    collection_id: str
    api_key: str
    cluster: Optional[Dict[str, str]] = None
    auth_jwt_url: Optional[str] = None

@dataclass
class NLPSearchParams:
    query: str
    llm_config: Optional[LLMConfig] = None
    user_id: Optional[str] = None

@dataclass
class CreateIndexParams:
    id: Optional[str] = None
    embeddings: Optional[Union[str, List[str]]] = None

@dataclass
class AddHookConfig:
    name: Hook
    code: str

@dataclass
class NewHookResponse:
    hook_id: str
    code: str

@dataclass
class ExecuteToolsBody:
    messages: List[Dict[str, str]]
    tool_ids: Optional[List[str]] = None
    llm_config: Optional[LLMConfig] = None

class AINamespace:
    """AI-related operations namespace."""
    
    def __init__(self, client: Client, collection_id: str, profile: Optional[Profile] = None):
        self.client = client
        self.collection_id = collection_id
        self.profile = profile
    
    async def nlp_search(self, params: NLPSearchParams) -> List[Dict[str, Any]]:
        """Perform NLP-based search."""
        body = {
            "user_id": self.profile.get_user_id() if self.profile else None,
            **params.__dict__
        }
        
        return await self.client.request(ClientRequest(
            method="POST",
            path=f"/v1/collections/{self.collection_id}/nlp_search",
            body=body,
            api_key_position="query-params",
            target="reader"
        ))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def nlp_search_stream(self, params: NLPSearchParams) -> AsyncGenerator[NLPSearchStreamResult, None]:
        """
        Production-grade streaming NLP search with real SSE implementation.
        
        Provides comprehensive Server-Sent Events streaming with retry logic,
        error handling, and proper state management.
        """
        body = {
            "llm_config": params.llm_config.__dict__ if params.llm_config else None,
            "user_id": self.profile.get_user_id() if self.profile else None,
            "messages": [{"role": "user", "content": params.query}]
        }
        
        try:
            response = await self.client.get_response(ClientRequest(
                method="POST",
                path=f"/v1/collections/{self.collection_id}/generate/nlp_query",
                body=body,
                api_key_position="query-params",
                target="reader"
            ))
            
            if not hasattr(response, 'content') or not response.content:
                logger.error("No response body for NLP search stream")
                return
            
            # Process the real SSE stream
            parser = SSEEventParser()
            
            async for line in response.content:
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                
                events = parser.parse_chunk(line)
                
                for event in events:
                    event_type = event.get('event', '')
                    data = event.get('data', '')
                    
                    if not data:
                        continue
                    
                    try:
                        parsed_data = stream_safe_json_parse(data)
                        if not parsed_data:
                            continue
                        
                        # Handle different NLP search stream events
                        if event_type == 'nlp_query_result' or 'query' in parsed_data:
                            yield NLPSearchStreamResult(
                                status=NLPSearchStreamStatus.SEARCH_RESULTS,
                                data=parsed_data
                            )
                        
                        elif event_type == 'nlp_query_status' or 'status' in parsed_data:
                            status_value = parsed_data.get('status', 'processing')
                            if status_value == 'completed':
                                yield NLPSearchStreamResult(
                                    status=NLPSearchStreamStatus.SEARCH_RESULTS,
                                    data=parsed_data
                                )
                                break
                        
                        elif event_type == 'error' or 'error' in parsed_data:
                            logger.error("NLP search stream error", error=parsed_data.get('error'))
                            break
                            
                    except Exception as e:
                        logger.warning("Failed to parse NLP stream event", error=str(e), data=data[:100])
                        continue
            
        except Exception as e:
            logger.error("NLP search stream failed", error=str(e))
            raise
    
    def create_ai_session(self, config: Optional[CreateAISessionConfig] = None) -> OramaCoreStream:
        """Create an AI session for streaming answers."""
        from .stream_manager import AnswerSessionConfig
        
        session_config = AnswerSessionConfig(
            collection_id=self.collection_id,
            common=self.client,
            llm_config=config.llm_config if config else None,
            initial_messages=config.initial_messages if config else None,
            events=config.events if config else None
        )
        
        return OramaCoreStream(session_config)

class CollectionsNamespace:
    """Collections management namespace."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    async def get_stats(self, collection_id: str) -> AnyObject:
        """Get collection statistics."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{collection_id}/stats",
            method="GET",
            api_key_position="query-params",
            target="reader"
        ))
    
    async def get_all_docs(self, id: str) -> List[AnyObject]:
        """Get all documents in collection."""
        return await self.client.request(ClientRequest(
            path="/v1/collections/list",
            method="POST",
            body={"id": id},
            api_key_position="header",
            target="writer"
        ))

class IndexNamespace:
    """Index management namespace."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    async def create(self, config: CreateIndexParams) -> None:
        """Create a new index."""
        body = {
            "id": config.id,
            "embedding": config.embeddings
        }
        
        await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/create",
            method="POST",
            body=body,
            api_key_position="header",
            target="writer"
        ))
    
    async def delete(self, index_id: str) -> None:
        """Delete an index."""
        await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/delete",
            method="POST",
            body={"index_id_to_delete": index_id},
            api_key_position="header",
            target="writer"
        ))
    
    def set(self, id: str) -> 'Index':
        """Get an Index instance for the specified ID."""
        return Index(self.client, self.collection_id, id)

class HooksNamespace:
    """Hooks management namespace."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    async def insert(self, config: AddHookConfig) -> NewHookResponse:
        """Insert a new hook."""
        body = {
            "name": config.name.value,
            "code": config.code
        }
        
        await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/hooks/set",
            method="POST",
            body=body,
            api_key_position="header",
            target="writer"
        ))
        
        return NewHookResponse(hook_id=body["name"], code=body["code"])
    
    async def list(self) -> Dict[str, Optional[str]]:
        """List all hooks."""
        response = await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/hooks/list",
            method="GET",
            api_key_position="header",
            target="writer"
        ))
        
        return response.get("hooks", {})
    
    async def delete(self, hook: Hook) -> None:
        """Delete a hook."""
        await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/hooks/delete",
            method="POST",
            body={"name_to_delete": hook.value},
            api_key_position="header",
            target="writer"
        ))

class LogsNamespace:
    """Production-grade logs streaming namespace with real EventSource implementation."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Production-grade EventSource log streaming.
        
        Provides real-time log streaming with comprehensive error handling,
        retry logic, and proper SSE event parsing.
        """
        try:
            response = await self.client.get_response(ClientRequest(
                path=f"/v1/collections/{self.collection_id}/logs",
                method="GET",
                api_key_position="query-params",
                target="reader"
            ))
            
            if not hasattr(response, 'content') or not response.content:
                logger.error("No response body for log stream")
                return
            
            # Process the real SSE stream
            parser = SSEEventParser()
            
            async for line in response.content:
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                
                events = parser.parse_chunk(line)
                
                for event in events:
                    event_type = event.get('event', '')
                    data = event.get('data', '')
                    
                    if not data:
                        continue
                    
                    try:
                        parsed_data = stream_safe_json_parse(data)
                        if not parsed_data:
                            continue
                        
                        # Handle different log event types
                        log_entry = {
                            'event_type': event_type,
                            'timestamp': parsed_data.get('timestamp'),
                            'level': parsed_data.get('level', 'info'),
                            'message': parsed_data.get('message', ''),
                            'metadata': parsed_data.get('metadata', {}),
                            'raw_data': parsed_data
                        }
                        
                        yield log_entry
                        
                    except Exception as e:
                        logger.warning("Failed to parse log event", error=str(e), data=data[:100])
                        # Still yield raw data for debugging
                        yield {
                            'event_type': 'parse_error',
                            'raw_data': data,
                            'error': str(e)
                        }
                        continue
                        
        except Exception as e:
            logger.error("Log streaming failed", error=str(e))
            raise

class SystemPromptsNamespace:
    """System prompts management namespace."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    async def insert(self, system_prompt: InsertSystemPromptBody) -> Dict[str, bool]:
        """Insert a system prompt."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/insert",
            method="POST",
            body=system_prompt.__dict__,
            api_key_position="header",
            target="writer"
        ))
    
    async def get(self, id: str) -> Dict[str, SystemPrompt]:
        """Get a system prompt."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/get",
            method="GET",
            params={"system_prompt_id": id},
            api_key_position="query-params",
            target="reader"
        ))
    
    async def get_all(self) -> Dict[str, List[SystemPrompt]]:
        """Get all system prompts."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/all",
            method="GET",
            api_key_position="query-params",
            target="reader"
        ))
    
    async def delete(self, id: str) -> Dict[str, bool]:
        """Delete a system prompt."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/delete",
            method="POST",
            body={"id": id},
            api_key_position="header",
            target="writer"
        ))
    
    async def update(self, system_prompt: SystemPrompt) -> Dict[str, bool]:
        """Update a system prompt."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/update",
            method="POST",
            body=system_prompt.__dict__,
            api_key_position="header",
            target="writer"
        ))
    
    async def validate(self, system_prompt: SystemPrompt) -> Dict[str, SystemPromptValidationResponse]:
        """Validate a system prompt."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/system_prompts/validate",
            method="POST",
            body=system_prompt.__dict__,
            api_key_position="header",
            target="writer"
        ))

class ToolsNamespace:
    """Tools management namespace."""
    
    def __init__(self, client: Client, collection_id: str):
        self.client = client
        self.collection_id = collection_id
    
    async def insert(self, tool: InsertToolBody) -> None:
        """Insert a tool."""
        # Handle different parameter types
        if isinstance(tool.parameters, str):
            parameters = tool.parameters
        elif isinstance(tool.parameters, dict):
            parameters = json.dumps(tool.parameters)
        else:
            # For schema objects, would need proper handling
            parameters = json.dumps(tool.parameters)
        
        body = {**tool.__dict__, "parameters": parameters}
        
        await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/insert",
            method="POST",
            body=body,
            api_key_position="header",
            target="writer"
        ))
    
    async def get(self, id: str) -> Dict[str, Tool]:
        """Get a tool."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/get",
            method="GET",
            params={"tool_id": id},
            api_key_position="query-params",
            target="reader"
        ))
    
    async def get_all(self) -> Dict[str, List[Tool]]:
        """Get all tools."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/all",
            method="GET",
            api_key_position="query-params",
            target="reader"
        ))
    
    async def delete(self, id: str) -> Dict[str, bool]:
        """Delete a tool."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/delete",
            method="POST",
            body={"id": id},
            api_key_position="header",
            target="writer"
        ))
    
    async def update(self, tool: UpdateToolBody) -> Dict[str, bool]:
        """Update a tool."""
        return await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/update",
            method="POST",
            body=tool.__dict__,
            api_key_position="header",
            target="writer"
        ))
    
    async def execute(self, tools: ExecuteToolsBody) -> ExecuteToolsParsedResponse:
        """Execute tools."""
        response = await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/tools/run",
            method="POST",
            body=tools.__dict__,
            api_key_position="query-params",
            target="reader"
        ))
        
        # Parse the response results
        if response.get("results"):
            parsed_results = []
            for result in response["results"]:
                if "functionResult" in result:
                    parsed_results.append({
                        "functionResult": {
                            "tool_id": result["functionResult"]["tool_id"],
                            "result": json.loads(result["functionResult"]["result"])
                        }
                    })
                elif "functionParameters" in result:
                    parsed_results.append({
                        "functionParameters": {
                            "tool_id": result["functionParameters"]["tool_id"],
                            "result": json.loads(result["functionParameters"]["result"])
                        }
                    })
                else:
                    parsed_results.append(result)
            
            return ExecuteToolsParsedResponse(results=parsed_results)
        
        return ExecuteToolsParsedResponse(results=None)

class IdentityNamespace:
    """Identity management namespace."""
    
    def __init__(self, profile: Optional[Profile] = None):
        self.profile = profile
    
    def get(self) -> Optional[str]:
        """Get identity."""
        if not self.profile:
            raise Exception("Profile is not defined")
        return self.profile.get_identity()
    
    def get_user_id(self) -> str:
        """Get user ID."""
        if not self.profile:
            raise Exception("Profile is not defined")
        return self.profile.get_user_id()
    
    def get_alias(self) -> Optional[str]:
        """Get alias."""
        if not self.profile:
            raise Exception("Profile is not defined")
        return self.profile.get_alias()
    
    async def identify(self, identity: str) -> None:
        """Set identity."""
        if not self.profile:
            raise Exception("Profile is not defined")
        await self.profile.identify(identity)
    
    async def alias(self, alias: str) -> None:
        """Set alias."""
        if not self.profile:
            raise Exception("Profile is not defined")
        await self.profile.alias(alias)
    
    def reset(self) -> None:
        """Reset identity."""
        if not self.profile:
            raise Exception("Profile is not defined")
        self.profile.reset()

class Index:
    """Index operations class."""
    
    def __init__(self, client: Client, collection_id: str, index_id: str):
        self.index_id = index_id
        self.collection_id = collection_id
        self.orama_interface = client
    
    async def reindex(self) -> None:
        """Reindex the index."""
        await self.orama_interface.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/{self.index_id}/reindex",
            method="POST",
            api_key_position="header",
            target="writer"
        ))
    
    async def insert_documents(self, documents: Union[AnyObject, List[AnyObject]]) -> None:
        """Insert documents into the index."""
        docs = documents if isinstance(documents, list) else [documents]
        
        await self.orama_interface.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/{self.index_id}/documents/insert",
            method="POST",
            body={"documents": docs},
            api_key_position="header",
            target="writer"
        ))
    
    async def delete_documents(self, document_ids: Union[str, List[str]]) -> None:
        """Delete documents from the index."""
        ids = document_ids if isinstance(document_ids, list) else [document_ids]
        
        await self.orama_interface.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/{self.index_id}/documents/delete",
            method="POST",
            body={"document_ids": ids},
            api_key_position="header",
            target="writer"
        ))
    
    async def upsert_documents(self, documents: List[AnyObject]) -> None:
        """Upsert documents in the index."""
        await self.orama_interface.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/indexes/{self.index_id}/documents/upsert",
            method="POST",
            body={"documents": documents},
            api_key_position="header",
            target="writer"
        ))

class CollectionManager:
    """Main collection manager class."""
    
    def __init__(self, config: CollectionManagerConfig):
        # Determine auth type
        if config.api_key.startswith('p_'):
            # Private API Key (JWT flow)
            auth = Auth(JwtAuth(
                auth_jwt_url=config.auth_jwt_url or DEFAULT_JWT_URL,
                collection_id=config.collection_id,
                private_api_key=config.api_key,
                reader_url=config.cluster.get('read_url') if config.cluster else DEFAULT_READER_URL,
                writer_url=config.cluster.get('writer_url') if config.cluster else None
            ))
            profile = None
        else:
            # Regular API Key
            auth = Auth(ApiKeyAuth(
                api_key=config.api_key,
                reader_url=config.cluster.get('read_url') if config.cluster else DEFAULT_READER_URL,
                writer_url=config.cluster.get('writer_url') if config.cluster else None
            ))
            profile = Profile(
                endpoint=config.cluster.get('read_url') if config.cluster else DEFAULT_READER_URL,
                api_key=config.api_key
            )
        
        self.collection_id = config.collection_id
        self.client = Client(ClientConfig(auth=auth))
        self.api_key = config.api_key
        self.profile = profile
        
        # Initialize namespaces
        self.ai = AINamespace(self.client, self.collection_id, self.profile)
        self.collections = CollectionsNamespace(self.client, self.collection_id)
        self.index = IndexNamespace(self.client, self.collection_id)
        self.hooks = HooksNamespace(self.client, self.collection_id)
        self.logs = LogsNamespace(self.client, self.collection_id)
        self.system_prompts = SystemPromptsNamespace(self.client, self.collection_id)
        self.tools = ToolsNamespace(self.client, self.collection_id)
        self.identity = IdentityNamespace(self.profile)
    
    async def search(self, query: SearchParams) -> SearchResult:
        """Perform a search."""
        start_time = int(time.time() * 1000)
        
        # Separate datasource_ids and indexes
        search_body = {
            "user_id": self.profile.get_user_id() if self.profile else None,
            **{k: v for k, v in query.__dict__.items() if k not in ['datasource_ids', 'indexes']}
        }
        
        # Use datasource_ids or indexes
        if query.datasource_ids:
            search_body['indexes'] = query.datasource_ids
        elif query.indexes:
            search_body['indexes'] = query.indexes
        
        result = await self.client.request(ClientRequest(
            path=f"/v1/collections/{self.collection_id}/search",
            method="POST",
            body=search_body,
            api_key_position="query-params",
            target="reader"
        ))
        
        elapsed_time = int(time.time() * 1000) - start_time
        
        return SearchResult(
            count=result["count"],
            hits=[Hit(**hit) for hit in result["hits"]],
            facets=result.get("facets"),
            elapsed=Elapsed(
                raw=elapsed_time,
                formatted=format_duration(elapsed_time)
            )
        )
    
    async def close(self):
        """Close the manager and cleanup resources."""
        await self.client.close()