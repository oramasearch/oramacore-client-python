"""
Orama Core Manager for collection management.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .common import Auth, Client, ClientConfig, ClientRequest, ApiKeyAuth
from .types import Language, EmbeddingsModel, AnyObject, Maybe
from .utils import create_random_string

@dataclass
class OramaCoreManagerConfig:
    url: str
    master_api_key: str

@dataclass
class CreateCollectionParams:
    id: str
    description: Optional[str] = None
    write_api_key: Optional[str] = None
    read_api_key: Optional[str] = None
    language: Optional[Language] = None
    embeddings_model: Optional[EmbeddingsModel] = None

@dataclass
class NewCollectionResponse:
    id: str
    write_api_key: str
    readonly_api_key: str
    description: Optional[str] = None

@dataclass
class CollectionIndexField:
    field_id: str
    field_path: str
    is_array: bool
    field_type: AnyObject

@dataclass
class CollectionIndex:
    id: str
    document_count: int
    fields: List[CollectionIndexField]
    automatically_chosen_properties: AnyObject

@dataclass
class GetCollectionsResponse:
    id: str
    document_count: int
    indexes: List[CollectionIndex]
    description: Optional[str] = None

class CollectionNamespace:
    """Collection management namespace."""
    
    def __init__(self, client: Client):
        self.client = client
    
    async def create(self, config: CreateCollectionParams) -> NewCollectionResponse:
        """Create a new collection."""
        body = {
            "id": config.id,
            "description": config.description,
            "write_api_key": config.write_api_key or create_random_string(32),
            "read_api_key": config.read_api_key or create_random_string(32),
        }
        
        if config.embeddings_model:
            body["embeddings_model"] = config.embeddings_model.value
        
        await self.client.request(ClientRequest(
            path="/v1/collections/create",
            method="POST",
            body=body,
            api_key_position="header",
            target="writer"
        ))
        
        return NewCollectionResponse(
            id=body["id"],
            description=body.get("description"),
            write_api_key=body["write_api_key"],
            readonly_api_key=body["read_api_key"]
        )
    
    async def list(self) -> List[GetCollectionsResponse]:
        """List all collections."""
        response = await self.client.request(ClientRequest(
            path="/v1/collections",
            method="GET",
            api_key_position="header",
            target="writer"
        ))
        
        return [GetCollectionsResponse(**item) for item in response]
    
    async def get(self, collection_id: str) -> GetCollectionsResponse:
        """Get a specific collection."""
        response = await self.client.request(ClientRequest(
            path=f"/v1/collections/{collection_id}",
            method="GET",
            api_key_position="header",
            target="writer"
        ))
        
        return GetCollectionsResponse(**response)
    
    async def delete(self, collection_id: str) -> None:
        """Delete a collection."""
        await self.client.request(ClientRequest(
            path="/v1/collections/delete",
            method="POST",
            body={"collection_id_to_delete": collection_id},
            api_key_position="header",
            target="writer"
        ))

class OramaCoreManager:
    """Main manager class for Orama Core operations."""
    
    def __init__(self, config: OramaCoreManagerConfig):
        auth = Auth(ApiKeyAuth(
            api_key=config.master_api_key,
            writer_url=config.url
        ))
        
        client = Client(ClientConfig(auth=auth))
        self.collection = CollectionNamespace(client)
    
    async def close(self):
        """Close the manager and cleanup resources."""
        await self.collection.client.close()