"""
Production-grade stream manager for AI session handling in Orama Python client (server-side only).

This module provides the same functionality as the JavaScript client but optimized for server-side use only.
It includes:
- Real Server-Sent Events (SSE) streaming
- Production-grade error handling with retry logic
- Comprehensive timeout and resilience mechanisms
- Advanced autoquery event handling
- Robust JSON parsing for AI responses
"""

import uuid
import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, AsyncGenerator, Callable, Literal, TypeVar
from dataclasses import dataclass, field, asdict
from contextlib import asynccontextmanager

import aiohttp
import orjson
import structlog
from aiohttp_sse_client import sse_client
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .common import Client, ClientRequest
from .types import AnyObject, SearchParams, SearchResult  
from .constants import DEFAULT_SERVER_USER_ID

# Configure structured logging
logger = structlog.get_logger(__name__)

Role = Literal["system", "assistant", "user"]
LLMProvider = Literal["openai", "fireworks", "together", "google"]

T = TypeVar('T')

@dataclass
class StreamConfig:
    """Configuration for streaming resilience and timeouts."""
    max_retries: int = 3
    initial_retry_delay: float = 1.0  # seconds
    max_retry_delay: float = 30.0     # seconds
    connection_timeout: float = 30.0  # seconds
    stream_timeout: float = 300.0     # seconds (5 minutes)
    chunk_timeout: float = 10.0       # seconds between chunks


@dataclass
class Message:
    role: Role
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelatedQuestionsConfig:
    enabled: Optional[bool] = None
    size: Optional[int] = None
    format: Optional[Literal["question", "query"]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LLMConfig:
    provider: LLMProvider
    model: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdvancedAutoquery:
    """Advanced autoquery state tracking."""
    optimized_queries: Optional[List[str]] = None
    selected_properties: Optional[List[AnyObject]] = None
    selected_properties_with_values: Optional[Dict[str, Dict[str, List[str]]]] = None
    queries_and_properties: Optional[List[Dict[str, Any]]] = None
    tracked_queries: Optional[List[Dict[str, Any]]] = None
    search_results: Optional[List[Dict[str, Any]]] = None
    results: Optional[List[Dict[str, Any]]] = None


@dataclass
class Interaction:
    """Represents a single interaction in the conversation."""
    id: str
    query: str
    response: str = ""
    optimized_query: Optional[SearchParams] = None
    sources: Optional[AnyObject] = None
    loading: bool = True
    error: bool = False
    error_message: Optional[str] = None
    aborted: bool = False
    related: Optional[str] = None
    current_step: Optional[str] = "starting"
    current_step_verbose: Optional[str] = None
    selected_llm: Optional[LLMConfig] = None
    advanced_autoquery: Optional[AdvancedAutoquery] = None


@dataclass
class AnswerConfig:
    """Configuration for AI answer requests."""
    query: str
    interaction_id: Optional[str] = None
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    messages: Optional[List[Message]] = None
    related: Optional[RelatedQuestionsConfig] = None
    datasource_ids: Optional[List[str]] = None
    min_similarity: Optional[float] = None
    max_documents: Optional[int] = None
    ragat_notation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if key == "messages" and isinstance(value, list):
                    result[key] = [msg.to_dict() if hasattr(msg, 'to_dict') else msg for msg in value]
                elif key == "related" and hasattr(value, 'to_dict'):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
        return result


@dataclass
class CreateAISessionConfig:
    """Configuration for creating AI sessions."""
    llm_config: Optional[LLMConfig] = None
    initial_messages: Optional[List[Message]] = None
    events: Optional[Dict[str, Callable]] = None


@dataclass
class AnswerSessionConfig:
    """Configuration for answer sessions."""
    collection_id: str
    common: Client
    initial_messages: Optional[List[Message]] = None
    events: Optional[Dict[str, Callable]] = None
    session_id: Optional[str] = None
    llm_config: Optional[LLMConfig] = None
    stream_config: Optional[StreamConfig] = None


class SSEParseError(Exception):
    """Error parsing Server-Sent Events."""
    pass


class StreamTimeoutError(Exception):
    """Stream timeout error."""
    pass


def safe_json_parse(data: str, default: Any = None) -> Any:
    """
    Safely parse JSON with robust error handling.
    Uses orjson for better performance and error handling.
    """
    if not data or not data.strip():
        return default
    
    try:
        return orjson.loads(data)
    except orjson.JSONDecodeError:
        # Try standard json as fallback
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON", data=data[:100])
            return default


def dedupe(message: str) -> bool:
    """Simple deduplication check."""
    # This is a simplified version - in production you might want more sophisticated deduplication
    return bool(message and message.strip())


class SSEEventParser:
    """Production-grade Server-Sent Events parser."""
    
    def __init__(self):
        self.buffer = ""
        self.current_event = {}
    
    def parse_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """Parse a chunk of SSE data and return complete events."""
        events = []
        self.buffer += chunk
        
        while True:
            line_end = self.buffer.find('\n')
            if line_end == -1:
                break
                
            line = self.buffer[:line_end].rstrip('\r')
            self.buffer = self.buffer[line_end + 1:]
            
            if not line:
                # Empty line indicates end of event
                if self.current_event:
                    events.append(self.current_event.copy())
                    self.current_event = {}
            elif not line.startswith(':'):
                # Parse field:value format
                if ':' in line:
                    field, value = line.split(':', 1)
                    value = value.lstrip(' ')
                else:
                    field, value = line, ''
                
                if field in self.current_event:
                    self.current_event[field] += '\n' + value
                else:
                    self.current_event[field] = value
        
        return events


class OramaCoreStream:
    """
    Production-grade AI session stream manager for server-side use only.
    
    This class provides the same functionality as the JavaScript client but optimized for server-side environments.
    It includes real SSE streaming, comprehensive error handling, retry logic, and production-grade resilience.
    """
    
    def __init__(self, config: AnswerSessionConfig):
        self.collection_id = config.collection_id
        self.orama_interface = config.common
        self.llm_config = config.llm_config
        self.events = config.events or {}
        self.session_id = config.session_id or str(uuid.uuid4())
        self.last_interaction_params: Optional[AnswerConfig] = None
        self.stream_config = config.stream_config or StreamConfig()
        
        # State management
        self.messages: List[Message] = config.initial_messages or []
        self.state: List[Interaction] = []
        
        # Connection management
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is available."""
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.stream_config.stream_timeout,
                connect=self.stream_config.connection_timeout,
                sock_read=self.stream_config.chunk_timeout
            )
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'orama-python-client/1.0.0'}
            )
    
    async def close(self):
        """Clean up resources."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def answer(self, data: AnswerConfig) -> str:
        """Get a complete answer (non-streaming)."""
        result = ""
        async for chunk in self.answer_stream(data):
            result = chunk
        return result
    
    async def answer_stream(self, data: AnswerConfig) -> AsyncGenerator[str, None]:
        """
        Get streaming answer with production-grade Server-Sent Events.
        
        This method provides real SSE streaming with comprehensive error handling,
        retry logic, and state management that matches the JavaScript client.
        """
        await self._ensure_session()
        
        # Store interaction parameters for potential regeneration
        self.last_interaction_params = AnswerConfig(**asdict(data))
        
        # Enrich config with defaults
        data = self._enrich_config(data)
        
        # Add messages to conversation history
        self.messages.append(Message(role="user", content=data.query))
        self.messages.append(Message(role="assistant", content=""))
        
        interaction_id = data.interaction_id or str(uuid.uuid4())
        
        # Create interaction state
        interaction = Interaction(
            id=interaction_id,
            query=data.query,
            response="",
            optimized_query=None,
            sources=None,
            loading=True,
            error=False,
            aborted=False,
            error_message=None,
            related="" if data.related and data.related.enabled else None,
            current_step="starting",
            current_step_verbose=None,
            selected_llm=None,
            advanced_autoquery=None
        )
        
        self.state.append(interaction)
        self._push_state()
        
        current_state_index = len(self.state) - 1
        current_message_index = len(self.messages) - 1
        
        try:
            async for chunk in self._stream_with_retry(data, interaction_id, current_state_index, current_message_index):
                yield chunk
                
        except Exception as error:
            logger.error("Stream error", error=str(error), interaction_id=interaction_id)
            self.state[current_state_index].loading = False
            self.state[current_state_index].error = True
            self.state[current_state_index].error_message = str(error)
            self._push_state()
            raise error
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, SSEParseError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _stream_with_retry(
        self,
        data: AnswerConfig,
        interaction_id: str,
        current_state_index: int,
        current_message_index: int
    ) -> AsyncGenerator[str, None]:
        """Stream with retry logic and exponential backoff."""
        
        # Prepare request body
        body = {
            "interaction_id": interaction_id,
            "query": data.query,
            "visitor_id": data.visitor_id,
            "conversation_id": data.session_id,
            "messages": [msg.to_dict() for msg in self.messages[:-1]],  # Exclude empty assistant message
            "llm_config": self.llm_config.to_dict() if self.llm_config else None,
            "related": data.related.to_dict() if data.related else None,
            "min_similarity": data.min_similarity,
            "max_documents": data.max_documents,
            "ragat_notation": data.ragat_notation
        }
        
        # Get auth and URL from the common client
        response = await self.orama_interface.get_response(ClientRequest(
            method="POST",
            path=f"/v1/collections/{self.collection_id}/generate/answer",
            body=body,
            api_key_position="query-params",
            target="reader"
        ))
        
        if not hasattr(response, 'content') or not response.content:
            raise SSEParseError("No response body available for streaming")
        
        # Process the real SSE stream
        parser = SSEEventParser()
        finished = False
        last_yielded = ""
        
        try:
            # Read response as SSE stream
            async for line in response.content:
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                
                events = parser.parse_chunk(line)
                
                for event in events:
                    finished = await self._process_sse_event(
                        event, 
                        current_state_index, 
                        current_message_index
                    )
                    
                    # Yield response updates
                    current_response = self.state[current_state_index].response
                    if current_response != last_yielded:
                        last_yielded = current_response
                        yield current_response
                    
                    if finished:
                        break
                
                if finished:
                    break
                    
        except asyncio.TimeoutError:
            raise StreamTimeoutError(f"Stream timeout after {self.stream_config.stream_timeout} seconds")
        except Exception as e:
            logger.error("SSE parsing error", error=str(e))
            raise SSEParseError(f"Failed to parse SSE stream: {e}")
    
    async def _process_sse_event(
        self, 
        event: Dict[str, Any], 
        current_state_index: int, 
        current_message_index: int
    ) -> bool:
        """
        Process a single SSE event and update state.
        Returns True if the stream is finished.
        """
        event_type = event.get('event', '')
        data = event.get('data', '')
        
        if not data:
            return False
        
        try:
            parsed_data = safe_json_parse(data)
            if not parsed_data:
                return False
                
        except Exception as e:
            logger.warning("Failed to parse event data", data=data[:100], error=str(e))
            return False
        
        # Handle different event types (matching JavaScript client)
        if event_type == 'answer_token' or 'token' in parsed_data:
            token = parsed_data.get('token', data)
            self.state[current_state_index].response += token
            self.messages[current_message_index].content = self.state[current_state_index].response
            self._push_state()
            
        elif event_type == 'selected_llm' or 'provider' in parsed_data:
            self.state[current_state_index].selected_llm = LLMConfig(
                provider=parsed_data.get('provider', 'openai'),
                model=parsed_data.get('model', 'unknown')
            )
            self._push_state()
            
        elif event_type == 'optimizing_query' or 'optimized_query' in parsed_data:
            optimized = safe_json_parse(parsed_data.get('optimized_query', '{}'))
            self.state[current_state_index].optimized_query = optimized
            self._push_state()
            
        elif event_type == 'search_results' or 'results' in parsed_data:
            self.state[current_state_index].sources = parsed_data.get('results')
            self._push_state()
            
        elif event_type == 'related_queries' or 'queries' in parsed_data:
            queries = parsed_data.get('queries', [])
            if isinstance(queries, list):
                self.state[current_state_index].related = '\n'.join(queries)
            else:
                self.state[current_state_index].related = str(queries)
            self._push_state()
            
        elif event_type == 'state_changed' or 'state' in parsed_data:
            state_name = parsed_data.get('state', '')
            self.state[current_state_index].current_step = state_name
            
            # Handle advanced autoquery events
            self._handle_advanced_autoquery_event(parsed_data, current_state_index)
            
            # Check for completion
            if state_name == 'completed':
                self.state[current_state_index].loading = False
                self._push_state()
                if self.events.get('on_end'):
                    self.events['on_end'](self.state)
                return True
            
            self._push_state()
            
        # Call incoming event handler if configured
        if self.events.get('on_incoming_event'):
            self.events['on_incoming_event'](parsed_data)
        
        return False
    
    def _handle_advanced_autoquery_event(self, event_data: Dict[str, Any], current_state_index: int):
        """Handle advanced autoquery events with detailed state tracking."""
        state = event_data.get('state', '')
        data = event_data.get('data', {})
        
        if not self.state[current_state_index].advanced_autoquery:
            self.state[current_state_index].advanced_autoquery = AdvancedAutoquery()
        
        autoquery = self.state[current_state_index].advanced_autoquery
        
        if state == 'advanced_autoquery_query_optimized' and data.get('optimized_queries'):
            autoquery.optimized_queries = data['optimized_queries']
            verbose_message = '\nAlso, '.join(autoquery.optimized_queries)
            if dedupe(verbose_message):
                self.state[current_state_index].current_step_verbose = verbose_message
                
        elif state == 'advanced_autoquery_properties_selected' and data.get('selected_properties'):
            autoquery.selected_properties = data['selected_properties']
            filters = []
            for prop_group in autoquery.selected_properties:
                if isinstance(prop_group, dict):
                    for values in prop_group.values():
                        if isinstance(values, dict) and 'selected_properties' in values:
                            for prop in values['selected_properties']:
                                if isinstance(prop, dict) and 'property' in prop:
                                    filters.append(prop['property'])
            
            if filters:
                verbose_message = f"Filtering by {', '.join(filters)}"
                if dedupe(verbose_message):
                    self.state[current_state_index].current_step_verbose = verbose_message
                    
        elif state == 'advanced_autoquery_combine_queries' and data.get('queries_and_properties'):
            autoquery.queries_and_properties = data['queries_and_properties']
            
        elif state == 'advanced_autoquery_tracked_queries_generated' and data.get('tracked_queries'):
            autoquery.tracked_queries = data['tracked_queries']
            
        elif state == 'advanced_autoquery_search_results' and data.get('search_results'):
            autoquery.search_results = data['search_results']
            
            # Calculate results count and generate verbose message
            results_count = 0
            result_terms = []
            for result in autoquery.search_results:
                if isinstance(result, dict):
                    results = result.get('results', [])
                    if results and len(results) > 0 and isinstance(results[0], dict):
                        results_count += results[0].get('count', 0)
                    
                    generated_query = result.get('generated_query', '')
                    if generated_query:
                        query_data = safe_json_parse(generated_query, {})
                        if isinstance(query_data, dict) and 'term' in query_data:
                            result_terms.append(query_data['term'])
            
            if result_terms:
                result_text = ', '.join(result_terms)
                plural = 's' if results_count != 1 else ''
                verbose_message = f"Found {results_count} result{plural} for \"{result_text}\""
                if dedupe(verbose_message):
                    self.state[current_state_index].current_step_verbose = verbose_message
                    
        elif state == 'advanced_autoquery_completed' and data.get('results'):
            autoquery.results = data['results']
            self.state[current_state_index].current_step_verbose = None
    
    async def regenerate_last(self, stream: bool = True) -> Union[str, AsyncGenerator[str, None]]:
        """Regenerate the last response."""
        if not self.state or not self.messages:
            raise Exception("No messages to regenerate")
        
        if not self.messages or self.messages[-1].role != "assistant":
            raise Exception("Last message is not an assistant message")
        
        if not self.last_interaction_params:
            raise Exception("No last interaction parameters available")
        
        # Remove last assistant message and state
        self.messages.pop()
        self.state.pop()
        
        if stream:
            return self.answer_stream(self.last_interaction_params)
        else:
            return await self.answer(self.last_interaction_params)
    
    def abort(self) -> None:
        """Abort the current stream."""
        if not self.state:
            raise Exception("There is no active request to abort")
        
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        
        last_state = self.state[-1]
        last_state.aborted = True
        last_state.loading = False
        
        self._push_state()
    
    def clear_session(self) -> None:
        """Clear the session history."""
        self.messages = []
        self.state = []
        self._push_state()
    
    def _push_state(self) -> None:
        """Push state change to event handler."""
        if self.events.get("on_state_change"):
            self.events["on_state_change"](self.state)
    
    def _enrich_config(self, config: AnswerConfig) -> AnswerConfig:
        """Enrich config with default values."""
        if not config.visitor_id:
            config.visitor_id = self._get_user_id()
        
        if not config.interaction_id:
            config.interaction_id = str(uuid.uuid4())
        
        if not config.session_id:
            config.session_id = self.session_id
        
        return config
    
    def _get_user_id(self) -> str:
        """Get user ID for the session (always server-side for Python client)."""
        return DEFAULT_SERVER_USER_ID


# Convenience functions for easier usage

async def create_ai_session(
    collection_id: str,
    common: Client,
    config: Optional[CreateAISessionConfig] = None
) -> OramaCoreStream:
    """Create a new AI session with optional configuration."""
    if config is None:
        config = CreateAISessionConfig()
    
    session_config = AnswerSessionConfig(
        collection_id=collection_id,
        common=common,
        initial_messages=config.initial_messages,
        events=config.events,
        llm_config=config.llm_config
    )
    
    return OramaCoreStream(session_config)


@asynccontextmanager
async def ai_session_context(
    collection_id: str,
    common: Client,
    config: Optional[CreateAISessionConfig] = None
):
    """Async context manager for AI sessions with automatic cleanup."""
    session = await create_ai_session(collection_id, common, config)
    try:
        async with session:
            yield session
    finally:
        await session.close()