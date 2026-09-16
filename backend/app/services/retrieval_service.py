import httpx
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document import DocumentChunk
from app.config import settings

logger = logging.getLogger(__name__)

class RetrievalService:
    _cached_matrix: Optional[np.ndarray] = None
    _cached_chunks: Optional[List[Dict[str, Any]]] = None

    def __init__(self, db: Session):
        self.db = db
        
    def _ensure_cache(self):
        """Pre-computes normalized 2D embeddings matrix for 5ms dot product searches."""
        if RetrievalService._cached_matrix is not None and RetrievalService._cached_chunks is not None:
            return

        chunks = self.db.execute(
            select(DocumentChunk).where(DocumentChunk.embedding.is_not(None))
        ).scalars().all()

        embeddings = []
        cached_meta = []
        for chunk in chunks:
            if chunk.embedding:
                embeddings.append(chunk.embedding)
                meta = chunk.metadata_ or {}
                cached_meta.append({
                    "guest": meta.get("guest", ""),
                    "episode_title": meta.get("episode_title", ""),
                    "source_file": meta.get("source_file", ""),
                    "youtube_url": meta.get("youtube_url", ""),
                    "publish_date": meta.get("publish_date", ""),
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                })

        if embeddings:
            mat = np.array(embeddings, dtype=np.float32)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            RetrievalService._cached_matrix = mat / norms
            RetrievalService._cached_chunks = cached_meta
            logger.info(f"Vector matrix cache initialized: {len(cached_meta)} chunks in RAM.")

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
        a_np = np.array(a, dtype=np.float32)
        b_np = np.array(b, dtype=np.float32)
        
        if not np.any(a_np) or not np.any(b_np):
            return 0.0
            
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        return float(dot_product / (norm_a * norm_b))

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most semantically relevant chunks for a given query.
        Uses vectorized dot product for millisecond-level execution.
        """
        query_emb = self._get_query_embedding(query)
        if not query_emb:
            return []

        self._ensure_cache()
        if RetrievalService._cached_matrix is None or not RetrievalService._cached_chunks:
            return []

        q_vec = np.array(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
        q_vec = q_vec / q_norm

        # Instant matrix dot product across all 10,360 vectors (~5ms)
        sims = RetrievalService._cached_matrix @ q_vec
        top_k = min(top_k, len(sims))
        top_indices = np.argsort(sims)[-top_k:][::-1]

        formatted_results = []
        for idx in top_indices:
            item = dict(RetrievalService._cached_chunks[idx])
            item["similarity"] = float(sims[idx])
            formatted_results.append(item)

        logger.info(
            f"Retrieval executed: query_length={len(query)}, scanned_chunks={len(RetrievalService._cached_chunks)}, "
            f"top_k={top_k}, top_match_similarity={formatted_results[0]['similarity'] if formatted_results else 0.0:.4f}"
        )
        return formatted_results
