"""
AI session and streaming example for Orama Python client.
"""

import asyncio
import os
from orama import CollectionManager, NLPSearchParams, LLMConfig

async def main():
    manager = CollectionManager({
        "collection_id": os.getenv("ORAMA_COLLECTION_ID", "your-collection-id"),
        "api_key": os.getenv("ORAMA_API_KEY", "your-api-key")
    })
    
    try:
        # Example 1: NLP Search
        print("=== NLP Search Example ===")
        nlp_results = await manager.ai.nlp_search(NLPSearchParams(
            query="What are the main benefits of using renewable energy sources?",
            llm_config=LLMConfig(provider="openai", model="gpt-4")
        ))
        
        print("NLP Search Results:")
        for result in nlp_results:
            print(f"Original Query: {result.get('original_query')}")
            print(f"Generated Query: {result.get('generated_query')}")
            print("-" * 40)
        
        # Example 2: Create AI Session for conversational search
        print("\n=== AI Session Example ===")
        session = manager.ai.create_ai_session({
            "llm_config": LLMConfig(provider="openai", model="gpt-3.5-turbo"),
            "events": {
                "on_state_change": lambda state: print(f"State changed: {len(state)} interactions")
            }
        })
        
        # Stream an answer
        print("Streaming answer...")
        print("Question: How does machine learning work?")
        print("Answer: ", end="", flush=True)
        
        full_answer = ""
        async for chunk in session.answer_stream({
            "query": "How does machine learning work in simple terms?"
        }):
            print(chunk[len(full_answer):], end="", flush=True)
            full_answer = chunk
        
        print("\n" + "-" * 50)
        print(f"Complete answer: {full_answer}")
        
        # Ask a follow-up question
        print("\nAsking follow-up question...")
        print("Question: Can you give me a practical example?")
        print("Answer: ", end="", flush=True)
        
        async for chunk in session.answer_stream({
            "query": "Can you give me a practical example?"
        }):
            print(chunk[len(full_answer):], end="", flush=True)
            full_answer = chunk
        
        print("\n" + "-" * 50)
        
        # Show conversation history
        print(f"Conversation history ({len(session.messages)} messages):")
        for msg in session.messages:
            print(f"{msg.role.capitalize()}: {msg.content[:100]}...")
        
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())