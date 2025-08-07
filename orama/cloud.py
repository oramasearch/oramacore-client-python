"""
Orama Cloud client functionality.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from .collection import CollectionManager, CollectionManagerConfig
from .types import SearchParams, SearchResult, AnyObject

@dataclass
class ProjectManagerConfig:
    project_id: str
    api_key: str
    cluster: Optional[Dict[str, str]] = None
    auth_jwt_url: Optional[str] = None

class DataSourceNamespace:
    """Data source operations namespace."""
    
    def __init__(self, index):
        self.index = index
    
    async def reindex(self) -> None:
        """Reindex the data source."""
        return await self.index.reindex()
    
    async def insert_documents(self, documents: Union[AnyObject, List[AnyObject]]) -> None:
        """Insert documents into the data source."""
        return await self.index.insert_documents(documents)
    
    async def delete_documents(self, document_ids: Union[str, List[str]]) -> None:
        """Delete documents from the data source."""
        return await self.index.delete_documents(document_ids)
    
    async def upsert_documents(self, documents: List[AnyObject]) -> None:
        """Upsert documents in the data source."""
        return await self.index.upsert_documents(documents)

class OramaCloud:
    """Orama Cloud client class."""
    
    def __init__(self, config: ProjectManagerConfig):
        # Use CollectionManager internally with project_id as collection_id
        self.client = CollectionManager(CollectionManagerConfig(
            collection_id=config.project_id,
            api_key=config.api_key,
            cluster=config.cluster,
            auth_jwt_url=config.auth_jwt_url
        ))
        
        # Expose all namespaces from CollectionManager
        self.identity = self.client.identity
        self.ai = self.client.ai
        self.collections = self.client.collections
        self.index = self.client.index
        self.hooks = self.client.hooks
        self.logs = self.client.logs
        self.system_prompts = self.client.system_prompts
        self.tools = self.client.tools
    
    async def search(self, params: Dict[str, Any]) -> SearchResult:
        """
        Perform a search with datasources parameter.
        Maps datasources to indexes for compatibility.
        """
        # Convert datasources to indexes for search
        search_params = SearchParams(**{
            k: v for k, v in params.items() if k != 'datasources'
        })
        
        if 'datasources' in params:
            search_params.indexes = params['datasources']
        
        return await self.client.search(search_params)
    
    def data_source(self, id: str) -> DataSourceNamespace:
        """Get a data source namespace for the specified ID."""
        index = self.client.index.set(id)
        return DataSourceNamespace(index)
    
    async def close(self):
        """Close the cloud client and cleanup resources."""
        await self.client.close()