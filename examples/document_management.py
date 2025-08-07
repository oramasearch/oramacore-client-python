"""
Document management example for Orama Python client.
"""

import asyncio
import os
from orama import CollectionManager

async def main():
    manager = CollectionManager({
        "collection_id": os.getenv("ORAMA_COLLECTION_ID", "your-collection-id"),
        "api_key": os.getenv("ORAMA_API_KEY", "your-api-key")
    })
    
    try:
        # Get an index reference
        index_id = "my-documents"  # Replace with your index ID
        index = manager.index.set(index_id)
        
        # Example documents
        documents = [
            {
                "id": "doc1",
                "title": "Introduction to Python",
                "content": "Python is a high-level programming language known for its simplicity and readability.",
                "category": "programming",
                "tags": ["python", "programming", "beginner"]
            },
            {
                "id": "doc2", 
                "title": "Machine Learning Basics",
                "content": "Machine learning is a subset of AI that enables computers to learn without explicit programming.",
                "category": "ai",
                "tags": ["machine-learning", "ai", "data-science"]
            },
            {
                "id": "doc3",
                "title": "Web Development with Python",
                "content": "Python offers several frameworks for web development including Django and Flask.",
                "category": "web-development",
                "tags": ["python", "web", "django", "flask"]
            }
        ]
        
        # Insert documents
        print("Inserting documents...")
        await index.insert_documents(documents)
        print(f"Successfully inserted {len(documents)} documents")
        
        # Wait a moment for indexing
        await asyncio.sleep(2)
        
        # Update a document using upsert
        print("\nUpdating document...")
        updated_doc = {
            "id": "doc1",
            "title": "Advanced Python Programming", 
            "content": "Python is a versatile language used in web development, data science, and automation.",
            "category": "programming",
            "tags": ["python", "programming", "advanced"]
        }
        await index.upsert_documents([updated_doc])
        print("Document updated successfully")
        
        # Search to verify the documents
        print("\nSearching for inserted documents...")
        from orama import SearchParams
        results = await manager.search(SearchParams(
            term="python",
            limit=10
        ))
        
        print(f"Found {results.count} documents containing 'python':")
        for hit in results.hits:
            doc = hit.document
            print(f"- {doc.get('title', 'No title')} (Score: {hit.score:.4f})")
        
        # Delete a document
        print("\nDeleting document...")
        await index.delete_documents(["doc3"])
        print("Document deleted successfully")
        
        # Verify deletion
        results_after_delete = await manager.search(SearchParams(
            term="flask",
            limit=10
        ))
        print(f"Search for 'flask' after deletion found {results_after_delete.count} results")
        
        # Reindex the collection (useful after bulk operations)
        print("\nReindexing collection...")
        await index.reindex()
        print("Reindexing completed")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())