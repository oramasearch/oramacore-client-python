"""
Server application example using Orama Python client.

This example demonstrates how to use the Orama client in a typical server environment,
such as a web API, background service, or data processing pipeline.
"""

import asyncio
import os
from typing import Dict, List, Any

from orama import CollectionManager, OramaCoreManager, SearchParams

class DocumentService:
    """
    Example service class showing how to integrate Orama in a server application.
    """
    
    def __init__(self, collection_id: str, api_key: str):
        self.manager = CollectionManager({
            "collection_id": collection_id,
            "api_key": api_key
        })
    
    async def search_documents(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for documents and return formatted results."""
        try:
            results = await self.manager.search(SearchParams(
                term=query,
                limit=limit,
                mode="hybrid"  # Use hybrid search for best results
            ))
            
            return {
                "query": query,
                "total_results": results.count,
                "search_time": results.elapsed.formatted if results.elapsed else "unknown",
                "documents": [
                    {
                        "id": hit.id,
                        "score": hit.score,
                        "title": hit.document.get("title", "Untitled"),
                        "summary": hit.document.get("content", "")[:200] + "..."
                    }
                    for hit in results.hits
                ]
            }
        except Exception as e:
            return {"error": str(e), "query": query}
    
    async def add_document(self, index_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Add a document to the collection."""
        try:
            index = self.manager.index.set(index_id)
            await index.insert_documents([document])
            
            return {
                "success": True,
                "message": f"Document '{document.get('id', 'unknown')}' added successfully"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_ai_answer(self, question: str) -> Dict[str, Any]:
        """Get an AI-powered answer to a question."""
        try:
            session = self.manager.ai.create_ai_session()
            answer = await session.answer({
                "query": question
            })
            
            return {
                "question": question,
                "answer": answer,
                "conversation_id": session.session_id
            }
        except Exception as e:
            return {"error": str(e), "question": question}
    
    async def close(self):
        """Clean up resources."""
        await self.manager.close()

async def main():
    """
    Example server application workflow.
    """
    # Configuration from environment variables (recommended for production)
    collection_id = os.getenv("ORAMA_COLLECTION_ID", "your-collection-id")
    api_key = os.getenv("ORAMA_API_KEY", "your-api-key")
    
    # Initialize the document service
    service = DocumentService(collection_id, api_key)
    
    try:
        print("🚀 Server-side Orama Client Example")
        print("=" * 50)
        
        # Example 1: Add documents (typical in data ingestion pipelines)
        print("\n📄 Adding sample documents...")
        documents = [
            {
                "id": "doc-001",
                "title": "Introduction to Machine Learning",
                "content": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience.",
                "category": "technology",
                "tags": ["ML", "AI", "technology"]
            },
            {
                "id": "doc-002", 
                "title": "Sustainable Energy Solutions",
                "content": "Renewable energy sources like solar and wind power are becoming increasingly important for environmental sustainability.",
                "category": "environment",
                "tags": ["renewable", "sustainability", "energy"]
            }
        ]
        
        for doc in documents:
            result = await service.add_document("main-index", doc)
            print(f"  - {result}")
        
        # Example 2: Search documents (typical in API endpoints)
        print("\n🔍 Searching documents...")
        search_queries = [
            "machine learning artificial intelligence",
            "renewable energy solutions",
            "technology sustainability"
        ]
        
        for query in search_queries:
            results = await service.search_documents(query, limit=5)
            if "error" not in results:
                print(f"\n  Query: '{query}'")
                print(f"  Found: {results['total_results']} results in {results['search_time']}")
                for doc in results["documents"]:
                    print(f"    - {doc['title']} (Score: {doc['score']:.3f})")
            else:
                print(f"  Error searching '{query}': {results['error']}")
        
        # Example 3: AI-powered Q&A (typical in chatbots or help systems)
        print("\n🤖 AI-powered answers...")
        questions = [
            "What is machine learning?",
            "How can renewable energy help the environment?"
        ]
        
        for question in questions:
            result = await service.get_ai_answer(question)
            if "error" not in result:
                print(f"\n  Q: {question}")
                print(f"  A: {result['answer']}")
            else:
                print(f"  Error with question '{question}': {result['error']}")
    
    except Exception as e:
        print(f"❌ Application error: {e}")
    
    finally:
        # Always clean up resources
        await service.close()
        print("\n✅ Application completed")

# Example of how to run this in different server contexts

async def web_api_example():
    """
    Example of how you might use this in a web API (FastAPI, Flask, etc.)
    """
    service = DocumentService(
        os.getenv("ORAMA_COLLECTION_ID", "your-collection-id"),
        os.getenv("ORAMA_API_KEY", "your-api-key")
    )
    
    try:
        # Simulating API endpoint behavior
        user_query = "machine learning algorithms"
        results = await service.search_documents(user_query)
        
        # In a real API, you'd return this as JSON response
        print(f"API Response: {results}")
        
    finally:
        await service.close()

async def batch_processing_example():
    """
    Example of batch processing documents (data pipelines, ETL jobs, etc.)
    """
    import time
    
    manager = OramaCoreManager({
        "url": os.getenv("ORAMA_URL", "https://your-orama-instance.com"),
        "master_api_key": os.getenv("ORAMA_MASTER_KEY", "your-master-key")
    })
    
    try:
        # Create a new collection for batch processing
        from orama.manager import CreateCollectionParams
        
        new_collection = await manager.collection.create(CreateCollectionParams(
            id=f"batch-{int(time.time())}",
            description="Batch processed documents"
        ))
        
        print(f"Created collection: {new_collection.id}")
        
        # Process documents in batches
        # In real scenario, this might come from a database, file system, etc.
        batch_documents = [
            {"id": f"batch-doc-{i}", "content": f"Document content {i}"}
            for i in range(100)
        ]
        
        collection_manager = CollectionManager({
            "collection_id": new_collection.id,
            "api_key": new_collection.write_api_key
        })
        
        index = collection_manager.index.set("batch-index")
        
        # Process in chunks of 10
        for i in range(0, len(batch_documents), 10):
            batch = batch_documents[i:i+10]
            await index.insert_documents(batch)
            print(f"Processed batch {i//10 + 1}: {len(batch)} documents")
        
        await collection_manager.close()
        
    except Exception as e:
        print(f"Batch processing error: {e}")

if __name__ == "__main__":
    # Run the main server application example
    asyncio.run(main())
    
    print("\n" + "="*50)
    print("Other usage examples:")
    print("- Uncomment web_api_example() for API usage")
    print("- Uncomment batch_processing_example() for batch processing")
    
    # Uncomment to run other examples:
    # asyncio.run(web_api_example())
    # asyncio.run(batch_processing_example())