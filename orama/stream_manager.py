"""
Stream manager for AI session handling in Orama Python client.
"""

import uuid
import asyncio
from typing import Dict, List, Any, Optional, Union, AsyncGenerator, Callable, Literal
from dataclasses import dataclass, field

from .common import Client, ClientRequest
from .types import AnyObject, SearchParams, SearchResult  
from .constants import DEFAULT_SERVER_USER_ID

Role = Literal["system", "assistant", "user"]

@dataclass
class Message:
    role: Role
    content: str

@dataclass
class RelatedQuestionsConfig:
    enabled: Optional[bool] = None
    size: Optional[int] = None
    format: Optional[Literal["question", "query"]] = None

@dataclass
class LLMConfig:
    provider: Literal["openai", "fireworks", "together", "google"]
    model: str

@dataclass
class AnswerConfig:
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

@dataclass
class Interaction:
    id: str
    query: str
    response: str = ""
    sources: Optional[AnyObject] = None
    loading: bool = True
    error: bool = False
    error_message: Optional[str] = None
    aborted: bool = False
    related: Optional[str] = None
    current_step: Optional[str] = None
    current_step_verbose: Optional[str] = None
    selected_llm: Optional[LLMConfig] = None
    optimized_query: Optional[SearchParams] = None
    advanced_autoquery: Optional[Dict[str, Any]] = None

@dataclass
class CreateAISessionConfig:
    llm_config: Optional[LLMConfig] = None
    initial_messages: Optional[List[Message]] = None
    events: Optional[Dict[str, Callable]] = None

@dataclass
class AnswerSessionConfig:
    collection_id: str
    common: Client
    initial_messages: Optional[List[Message]] = None
    events: Optional[Dict[str, Callable]] = None
    session_id: Optional[str] = None
    llm_config: Optional[LLMConfig] = None

class OramaCoreStream:
    """AI session stream manager."""
    
    def __init__(self, config: AnswerSessionConfig):
        self.collection_id = config.collection_id
        self.orama_interface = config.common
        self.llm_config = config.llm_config
        self.events = config.events
        self.session_id = config.session_id or str(uuid.uuid4())
        self.last_interaction_params: Optional[AnswerConfig] = None
        self.abort_event: Optional[asyncio.Event] = None
        
        self.messages: List[Message] = config.initial_messages or []
        self.state: List[Interaction] = []
    
    async def answer(self, data: AnswerConfig) -> str:
        """Get a complete answer (non-streaming)."""
        result = ""
        async for chunk in self.answer_stream(data):
            result = chunk
        return result
    
    async def answer_stream(self, data: AnswerConfig) -> AsyncGenerator[str, None]:
        """Get streaming answer."""
        self.last_interaction_params = data.copy() if hasattr(data, 'copy') else AnswerConfig(**data.__dict__)
        
        data = self._enrich_config(data)
        self.abort_event = asyncio.Event()
        
        self.messages.append(Message(role="user", content=data.query))
        self.messages.append(Message(role="assistant", content=""))
        
        interaction_id = data.interaction_id or str(uuid.uuid4())
        
        self.state.append(Interaction(
            id=interaction_id,
            query=data.query,
            response="",
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
        ))
        
        self._push_state()
        
        current_state_index = len(self.state) - 1
        current_message_index = len(self.messages) - 1
        
        try:
            body = {
                "interaction_id": interaction_id,
                "query": data.query,
                "visitor_id": data.visitor_id,
                "conversation_id": data.session_id,
                "messages": [msg.__dict__ for msg in self.messages[:-1]],  # Exclude empty assistant message
                "llm_config": self.llm_config.__dict__ if self.llm_config else None,
                "related": data.related.__dict__ if data.related else None,
                "min_similarity": data.min_similarity,
                "max_documents": data.max_documents,
                "ragat_notation": data.ragat_notation
            }
            
            response = await self.orama_interface.get_response(ClientRequest(
                method="POST",
                path=f"/v1/collections/{self.collection_id}/generate/answer",
                body=body,
                api_key_position="query-params",
                target="reader"
            ))
            
            if not response.content:
                raise Exception("No response body")
            
            # Simplified stream processing (would need proper SSE parsing in production)
            finished = False
            last_yielded = ""
            
            # This is a simplified version - in production you'd need to implement
            # proper SSE event stream parsing similar to the TypeScript version
            while not finished and not self.abort_event.is_set():
                # Simulate streaming response processing
                current_response = self.state[current_state_index].response
                
                if current_response != last_yielded:
                    last_yielded = current_response
                    yield current_response
                
                # In real implementation, this would process actual SSE events
                await asyncio.sleep(0.01)
                
                # Mock completion for this simplified version
                if len(current_response) > 0:
                    finished = True
                    self.state[current_state_index].loading = False
                    self._push_state()
        
        except Exception as error:
            if self.abort_event and self.abort_event.is_set():
                self.state[current_state_index].loading = False
                self.state[current_state_index].aborted = True
                self._push_state()
                return
            
            self.state[current_state_index].loading = False
            self.state[current_state_index].error = True
            self.state[current_state_index].error_message = str(error)
            self._push_state()
            raise error
    
    async def regenerate_last(self, stream: bool = True) -> Union[str, AsyncGenerator[str, None]]:
        """Regenerate the last response."""
        if not self.state or not self.messages:
            raise Exception("No messages to regenerate")
        
        if not self.messages or self.messages[-1].role != "assistant":
            raise Exception("Last message is not an assistant message")
        
        # Remove last assistant message and state
        self.messages.pop()
        self.state.pop()
        
        if not self.last_interaction_params:
            raise Exception("No last interaction parameters available")
        
        if stream:
            return self.answer_stream(self.last_interaction_params)
        else:
            return await self.answer(self.last_interaction_params)
    
    def abort(self) -> None:
        """Abort the current stream."""
        if not self.abort_event:
            raise Exception("No active request to abort")
        
        if not self.state:
            raise Exception("There is no active request to abort")
        
        self.abort_event.set()
        
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
        if self.events and "on_state_change" in self.events:
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
        """Get user ID for the session."""
        # Always use server user ID for server-side Python client
        return DEFAULT_SERVER_USER_ID