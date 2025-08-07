"""
Basic search example for Orama Python client.
"""

import asyncio
import os
from orama import CollectionManager, SearchParams

async def main():
    # Initialize the collection manager
    # You can set these as environment variables or pass them directly
    manager = CollectionManager({
        "collection_id": os.getenv("ORAMA_COLLECTION_ID", "your-collection-id"),
        "api_key": os.getenv("ORAMA_API_KEY", "your-api-key"),
        # Optional: specify custom cluster URLs
        # "cluster": {
        #     "read_url": "https://your-reader.orama.com",
        #     "writer_url": "https://your-writer.orama.com"
        # }
    })
    
    try:
        # Perform a basic search
        print("Performing basic search...")
        results = await manager.search(SearchParams(
            term="python programming",
            limit=5,
            mode="fulltext"  # or "vector", "hybrid", "auto"
        ))
        
        print(f"Found {results.count} results in {results.elapsed.formatted}")
        print("-" * 50)
        
        for i, hit in enumerate(results.hits, 1):
            print(f"{i}. Score: {hit.score:.4f}")
            print(f"   ID: {hit.id}")
            print(f"   Document: {hit.document}")
            print("-" * 30)
        
        # Perform a more complex search with filters
        print("\nPerforming filtered search...")
        filtered_results = await manager.search(SearchParams(
            term="machine learning",
            limit=3,
            where={"category": "technology"},  # Example filter
            properties=["title", "content"]    # Search only in specific fields
        ))
        
        print(f"Filtered search found {filtered_results.count} results")
        
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        # Always close the manager to clean up resources
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())