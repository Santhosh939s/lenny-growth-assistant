from app.db.session import SessionLocal
from app.services.retrieval_service import RetrievalService

def main():
    queries = [
        "How should a startup decide what product metrics to focus on?",
        "How do great product teams prioritize what to build?",
        "What makes a good product onboarding experience?"
    ]
    
    db = SessionLocal()
    try:
        service = RetrievalService(db)
        
        for i, q in enumerate(queries, 1):
            print(f"\n--- Query {i}: '{q}' ---")
            results = service.retrieve(q, top_k=3)
            for j, res in enumerate(results, 1):
                print(f"Result {j}: [Title: {res.get('episode_title')}] [Guest: {res.get('guest')}] (Score: {res['similarity']:.4f})")
                print(f"Text: {res['text'][:200]}...")
                print()
    finally:
        db.close()

if __name__ == "__main__":
    main()
