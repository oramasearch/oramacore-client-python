# Orama Python Client

Python client for OramaCore and Orama Cloud.

## Installation

### Basic Installation

```bash
pip install oramacore-client
```

### From Source

```bash
git clone https://github.com/oramasearch/oramacore-client-python.git
cd oramacore-client-python
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/oramasearch/oramacore-client-python.git
cd oramacore-client-python
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

### Production Installation

For production deployments with pinned versions:

```bash
pip install -r requirements-prod.txt
```

### Optional Features

For enhanced functionality (caching, monitoring, performance):

```bash
pip install -r requirements-optional.txt
```

### Installation Helper

You can also use the provided installation script for easier setup:

```bash
# Basic installation
python install.py basic

# Development installation
python install.py dev

# Production installation
python install.py prod

# With optional features
python install.py optional

# Everything (dev + optional)
python install.py all
```

## Quick Start

### Basic Usage

```python
import asyncio
from orama import CollectionManager, SearchParams

async def main():
    # Initialize the collection manager
    manager = CollectionManager({
        "collection_id": "your-collection-id",
        "api_key": "your-api-key"
    })

    # Perform a search
    results = await manager.search(SearchParams(
        term="search query",
        limit=10
    ))

    print(f"Found {results.count} results")
    for hit in results.hits:
        print(f"Score: {hit.score}, Document: {hit.document}")

    # Close the manager
    await manager.close()

# Run the async function
asyncio.run(main())
```

### Collection Management

```python
import asyncio
from orama import OramaCoreManager, CreateCollectionParams

async def main():
    # Initialize the core manager
    manager = OramaCoreManager({
        "url": "https://your-orama-instance.com",
        "master_api_key": "your-master-key"
    })

    # Create a new collection
    collection = await manager.collection.create(
        CreateCollectionParams(
            id="my-collection",
            description="My search collection"
        )
    )

    print(f"Created collection: {collection.id}")

asyncio.run(main())
```

### Document Management

```python
import asyncio
from orama import CollectionManager

async def main():
    manager = CollectionManager({
        "collection_id": "your-collection-id",
        "api_key": "your-api-key"
    })

    # Get an index reference
    index = manager.index.set("your-index-id")

    # Insert documents
    await index.insert_documents([
        {"id": "1", "title": "Document 1", "content": "Content 1"},
        {"id": "2", "title": "Document 2", "content": "Content 2"}
    ])

    # Update documents
    await index.upsert_documents([
        {"id": "1", "title": "Updated Document 1", "content": "Updated content"}
    ])

    # Delete documents
    await index.delete_documents(["2"])

    await manager.close()

asyncio.run(main())
```

### AI-Powered Search

```python
import asyncio
from orama import CollectionManager, NLPSearchParams

async def main():
    manager = CollectionManager({
        "collection_id": "your-collection-id",
        "api_key": "your-api-key"
    })

    # Perform NLP search
    results = await manager.ai.nlp_search(
        NLPSearchParams(
            query="What are the benefits of renewable energy?"
        )
    )

    print("NLP Search results:", results)

    # Create an AI session for conversational search
    session = manager.ai.create_ai_session()

    # Stream an answer
    async for chunk in session.answer_stream({
        "query": "Explain machine learning in simple terms"
    }):
        print(chunk, end="", flush=True)

    await manager.close()

asyncio.run(main())
```

### Cloud Integration

```python
import asyncio
from orama import OramaCloud

async def main():
    # Initialize Orama Cloud client
    cloud = OramaCloud({
        "project_id": "your-project-id",
        "api_key": "your-api-key"
    })

    # Search across datasources
    results = await cloud.search({
        "term": "search query",
        "datasources": ["datasource-1", "datasource-2"]
    })

    print(f"Found {results.count} results")

    # Manage a specific datasource
    datasource = cloud.data_source("datasource-1")
    await datasource.insert_documents([
        {"title": "New document", "content": "Document content"}
    ])

    await cloud.close()

asyncio.run(main())
```

## API Reference

### CollectionManager

Main class for interacting with Orama collections.

#### Methods

- `search(params: SearchParams) -> SearchResult`: Perform a search
- `ai.nlp_search(params: NLPSearchParams) -> List[Dict]`: NLP-powered search
- `ai.create_ai_session(config?) -> OramaCoreStream`: Create AI session
- `index.set(id: str) -> Index`: Get index reference
- `close()`: Close the manager

### OramaCoreManager

Class for managing Orama collections at the cluster level.

#### Methods

- `collection.create(params: CreateCollectionParams) -> NewCollectionResponse`: Create collection
- `collection.list() -> List[GetCollectionsResponse]`: List collections
- `collection.get(id: str) -> GetCollectionsResponse`: Get collection
- `collection.delete(id: str)`: Delete collection

### OramaCloud

High-level client for Orama Cloud.

#### Methods

- `search(params: Dict) -> SearchResult`: Search across datasources
- `data_source(id: str) -> DataSourceNamespace`: Get datasource reference

### Index

Class for managing documents in an index.

#### Methods

- `insert_documents(docs: Union[Dict, List[Dict]])`: Insert documents
- `upsert_documents(docs: List[Dict])`: Upsert documents
- `delete_documents(ids: Union[str, List[str]])`: Delete documents
- `reindex()`: Reindex the collection

## Configuration

### Authentication

The client supports two authentication methods:

1. **API Key Authentication**: Use your collection's API key
2. **Private API Key (JWT)**: Use a private API key that starts with `p_`

### Environment Variables

You can also configure the client using environment variables:

- `ORAMA_API_KEY`: Your API key
- `ORAMA_COLLECTION_ID`: Your collection ID
- `ORAMA_ENDPOINT`: Custom endpoint URL

### Server-Side Usage

This client is designed specifically for server-side use in Python applications. It does not include browser-specific functionality like localStorage or sendBeacon. All user identification is handled through API keys and server-generated UUIDs.

## Error Handling

```python
import asyncio
from orama import CollectionManager, SearchParams

async def main():
    manager = CollectionManager({
        "collection_id": "your-collection-id",
        "api_key": "your-api-key"
    })

    try:
        results = await manager.search(SearchParams(term="query"))
        print(results)
    except Exception as e:
        print(f"Search failed: {e}")
    finally:
        await manager.close()

asyncio.run(main())
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the AGPLv3 License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [https://docs.orama.com](https://docs.orama.com)
- GitHub Issues: [https://github.com/oramasearch/oramacore-client-python/issues](https://github.com/oramasearch/oramacore-client-python/issues)
- Community: [https://orama.to/slack](https://orama.to/slack)
