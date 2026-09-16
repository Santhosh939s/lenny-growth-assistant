import httpx
import numpy as np
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document import DocumentChunk
from app.config import settings

logger = logging.getLogger(__name__)

class RetrievalService:
    def __init__(self, db: Session):
        self.db = db
        
    def _get_query_embedding(self, query: str) -> List[float]:
        try:
            resp = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "prompt": query
                },
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            return []

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors using numpy."""
        a_np = np.array(a)
        b_np = np.array(b)
        
        # Avoid division by zero
        if not np.any(a_np) or not np.any(b_np):
            return 0.0
            
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        return float(dot_product / (norm_a * norm_b))

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most semantically relevant chunks for a given query.
        """
        query_emb = self._get_query_embedding(query)
        if not query_emb:
            return []

        # Fetch all chunks from DB that have an embedding
        # On a larger DB, we would use pgvector. Here we do an in-memory scan.
        all_chunks = self.db.execute(
            select(DocumentChunk).where(DocumentChunk.embedding.is_not(None))
        ).scalars().all()

        results = []
        for chunk in all_chunks:
            if chunk.embedding:
                sim = self._cosine_similarity(query_emb, chunk.embedding)
                results.append((sim, chunk))

        # Sort by similarity descending
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Take top K
        top_results = results[:top_k]
        
        # Format response
        formatted_results = []
        for sim, chunk in top_results:
            meta = chunk.metadata_ or {}
            formatted_results.append({
                "guest": meta.get("guest", ""),
                "episode_title": meta.get("episode_title", ""),
                "source_file": meta.get("source_file", ""),
                "youtube_url": meta.get("youtube_url", ""),
                "publish_date": meta.get("publish_date", ""),
                "chunk_index": chunk.chunk_index,
                "similarity": sim,
                "text": chunk.text,
            })

        logger.info(
            f"Retrieval executed: query_length={len(query)}, scanned_chunks={len(all_chunks)}, "
            f"top_k={top_k}, top_match_similarity={formatted_results[0]['similarity'] if formatted_results else 0.0:.4f}"
        )
        return formatted_results
