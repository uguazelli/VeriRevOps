import os
import sys
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables (API keys)
load_dotenv()

from src.services.rerank import rerank_documents

def test_rerank():
    query = "Who is the CEO of the company?"
    documents = [
        {"id": "doc1", "content": "The CEO of VeriCorp is Jane Smith.", "filename": "about.txt"},
        {"id": "doc2", "content": "The weather in San Francisco is foggy today.", "filename": "weather.txt"},
        {"id": "doc3", "content": "Our office hours are from 9 AM to 5 PM.", "filename": "contact.txt"},
    ]

    print(f"--- Reranking query: '{query}' ---")
    results = rerank_documents(query, documents, top_k=2)

    for i, res in enumerate(results):
        print(f"Result {i+1}: {res['id']} (Score: {res.get('rerank_score', 'N/A')})")
        print(f"Content: {res['content'][:100]}...")
        print("-" * 30)

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not found in environment.")
    else:
        test_rerank()
