"""
Type definitions for Orama Python client.
"""

from typing import Dict, List, Optional, Union, Any, TypeVar, Generic, Literal
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T')

# Type aliases
Nullable = Optional[T]
Maybe = Optional[T]
AnyObject = Dict[str, Any]

# Language enum
class Language(str, Enum):
    ARABIC = "arabic"
    BULGARIAN = "bulgarian"
    CHINESE = "chinese"
    DANISH = "danish"
    DUTCH = "dutch"
    GERMAN = "german"
    GREEK = "greek"
    ENGLISH = "english"
    ESTONIAN = "estonian"
    SPANISH = "spanish"
    FINNISH = "finnish"
    FRENCH = "french"
    IRISH = "irish"
    HINDI = "hindi"
    HUNGARIAN = "hungarian"
    ARMENIAN = "armenian"
    INDONESIAN = "indonesian"
    ITALIAN = "italian"
    JAPANESE = "japanese"
    KOREAN = "korean"
    LITUANIAN = "lituanian"
    NEPALI = "nepali"
    NORWEGIAN = "norwegian"
    PORTUGUESE = "portuguese"
    ROMANIAN = "romanian"
    RUSSIAN = "russian"
    SANSKRIT = "sanskrit"
    SLOVENIAN = "slovenian"
    SERBIAN = "serbian"
    SWEDISH = "swedish"
    TAMIL = "tamil"
    TURKISH = "turkish"
    UKRAINIAN = "ukrainian"

# Embeddings model enum
class EmbeddingsModel(str, Enum):
    E5_MULTILANG_SMALL = "E5MultilangualSmall"
    E5_MULTILANG_BASE = "E5MultilangualBase"
    E5_MULTILANG_LARGE = "E5MultilangualLarge"
    BGE_SMALL = "BGESmall"
    BGE_BASE = "BGEBase"
    BGE_LARGE = "BGELarge"

@dataclass
class EmbeddingsConfig:
    model: Optional[EmbeddingsModel]
    document_fields: Optional[List[str]]

# Hook enum
class Hook(str, Enum):
    BEFORE_ANSWER = "BeforeAnswer"
    BEFORE_RETRIEVAL = "BeforeRetrieval"

# Search mode enum
class SearchMode(str, Enum):
    FULLTEXT = "fulltext"
    VECTOR = "vector"
    HYBRID = "hybrid"
    AUTO = "auto"

@dataclass
class SearchParams:
    term: str
    mode: Optional[SearchMode] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    properties: Optional[List[str]] = None
    where: Optional[AnyObject] = None
    facets: Optional[AnyObject] = None
    indexes: Optional[List[str]] = None
    datasource_ids: Optional[List[str]] = None
    exact: Optional[bool] = None
    threshold: Optional[float] = None
    tolerance: Optional[int] = None
    user_id: Optional[str] = None

CloudSearchParams = SearchParams  # Omit indexes field functionality handled in implementation

@dataclass
class Hit(Generic[T]):
    id: str
    score: float
    document: T
    datasource_id: Optional[str] = None

@dataclass
class Elapsed:
    raw: int
    formatted: str

@dataclass
class SearchResult(Generic[T]):
    count: int
    hits: List[Hit[T]]
    facets: Optional[AnyObject] = None
    elapsed: Optional[Elapsed] = None

@dataclass
class Trigger:
    id: str
    name: str
    description: str
    response: str
    segment_id: Optional[str] = None

@dataclass
class Segment:
    id: str
    name: str
    description: str
    goal: Optional[str] = None

@dataclass
class InsertSegmentBody:
    name: str
    description: str
    id: Optional[str] = None
    goal: Optional[str] = None

@dataclass
class InsertTriggerBody:
    name: str
    description: str
    response: str
    segment_id: str
    id: Optional[str] = None

@dataclass
class InsertSegmentResponse:
    success: bool
    id: str
    segment: Segment

@dataclass
class InsertTriggerResponse:
    success: bool
    id: str
    trigger: Trigger

@dataclass
class UpdateTriggerResponse:
    success: bool
    trigger: Trigger

@dataclass
class SystemPrompt:
    id: str
    name: str
    prompt: str
    usage_mode: Literal["automatic", "manual"]

@dataclass
class InsertSystemPromptBody:
    name: str
    prompt: str
    usage_mode: Literal["automatic", "manual"]
    id: Optional[str] = None

@dataclass
class SystemPromptValidationResponse:
    security: Dict[str, Any]
    technical: Dict[str, Any]
    overall_assessment: Dict[str, Any]

@dataclass
class Tool:
    id: str
    name: str
    description: str
    parameters: str
    system_prompt: Optional[str] = None

@dataclass
class InsertToolBody:
    id: str
    description: str
    parameters: Union[str, AnyObject, Any]  # ZodType equivalent
    code: Optional[str] = None
    system_prompt: Optional[str] = None

@dataclass
class UpdateToolBody:
    id: str
    description: Optional[str] = None
    parameters: Optional[Union[str, AnyObject, Any]] = None
    code: Optional[str] = None

@dataclass
class FunctionCall:
    name: str
    arguments: str

@dataclass
class FunctionCallParsed:
    name: str
    arguments: AnyObject

@dataclass
class ExecuteToolsResponse:
    results: Optional[List[FunctionCall]]

@dataclass
class ExecuteToolsFunctionResult(Generic[T]):
    function_result: Dict[str, Any]

@dataclass
class ExecuteToolsParametersResult(Generic[T]):
    function_parameters: Dict[str, Any]

ExecuteToolsResult = Union[ExecuteToolsFunctionResult[T], ExecuteToolsParametersResult[T]]

@dataclass
class ExecuteToolsParsedResponse(Generic[T]):
    results: Optional[List[ExecuteToolsResult[T]]]

@dataclass
class NLPSearchResult(Generic[T]):
    original_query: str
    generated_query: SearchParams
    results: List[Dict[str, Any]]

class NLPSearchStreamStatus(str, Enum):
    INIT = "INIT"
    OPTIMIZING_QUERY = "OPTIMIZING_QUERY"
    QUERY_OPTIMIZED = "QUERY_OPTIMIZED"
    SELECTING_PROPS = "SELECTING_PROPS"
    SELECTED_PROPS = "SELECTED_PROPS"
    COMBINING_QUERIES_AND_PROPERTIES = "COMBINING_QUERIES_AND_PROPERTIES"
    COMBINED_QUERIES_AND_PROPERTIES = "COMBINED_QUERIES_AND_PROPERTIES"
    GENERATING_QUERIES = "GENERATING_QUERIES"
    GENERATED_QUERIES = "GENERATED_QUERIES"
    SEARCHING = "SEARCHING"
    SEARCH_RESULTS = "SEARCH_RESULTS"

@dataclass
class GeneratedQuery:
    index: int
    original_query: str
    generated_query: Dict[str, Any]

SelectedProperties = Dict[str, Dict[str, List[Any]]]

@dataclass
class CombinedQueryAndProperties:
    query: str
    properties: SelectedProperties
    filter_properties: Dict[str, Any]

@dataclass
class NLPSearchStreamResult(Generic[T]):
    status: NLPSearchStreamStatus
    data: Optional[Union[T, List[T], List[GeneratedQuery], List[SelectedProperties], List[CombinedQueryAndProperties]]] = None