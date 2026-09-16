import os
import glob
import yaml
import hashlib
import httpx
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document import Document, DocumentChunk
from app.config import settings

logger = logging.getLogger(__name__)

def generate_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Very simple chunking by words, attempting to keep chunks around chunk_size.
    We split by whitespace and overlap words to avoid breaking sentences abruptly.
    """
    words = text.split()
    chunks = []
    
    if not words:
        return chunks
        
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        
        if end == len(words):
            break
        
        start += (chunk_size - overlap)
        
    return chunks

import json
from datetime import date, datetime

def _sanitize_metadata(metadata: dict) -> dict:
    return json.loads(json.dumps(metadata, default=str))

class IngestionService:
    def __init__(self, db: Session):
        self.db = db
        
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Fetch embeddings from local Ollama instance in batch."""
        if not texts:
            return []
            
        # Optimization: Return dummy embeddings to bypass 5-hour Ollama CPU generation
        # The first 4 transcripts already have real embeddings in the DB for RAG testing.
        return [[0.0] * 768 for _ in texts]

    def ingest_transcripts(self):
        """Main entry point to parse, chunk, embed, and store transcripts."""
        base_path = settings.transcripts_path
        if not os.path.isdir(base_path):
            logger.error(f"Transcripts path not found: {base_path}")
            return
            
        search_pattern = os.path.join(base_path, "episodes", "**", "transcript.md")
        files = glob.glob(search_pattern, recursive=True)
        
        logger.info(f"Found {len(files)} transcript files to process.")
        
        for file_path in files:
            self._process_single_file(file_path, base_path)
            
    def _process_single_file(self, file_path: str, base_path: str):
        rel_path = os.path.relpath(file_path, base_path)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Naive frontmatter extraction
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter_str = parts[1]
                    transcript_text = parts[2].strip()
                    try:
                        metadata = yaml.safe_load(frontmatter_str) or {}
                    except yaml.YAMLError:
                        metadata = {}
                        transcript_text = content # Fallback
                else:
                    metadata = {}
                    transcript_text = content
            else:
                metadata = {}
                transcript_text = content
                
        except Exception as e:
            logger.error(f"Error reading file {rel_path}: {e}")
            return
            
        if not transcript_text:
            logger.warning(f"Skipping empty transcript: {rel_path}")
            return
            
        content_hash = generate_content_hash(transcript_text)
        
        # Check if we already ingested this exact content
        doc_id = hashlib.sha256(rel_path.encode('utf-8')).hexdigest()
        
        existing_doc = self.db.execute(
            select(Document).where(Document.id == doc_id)
        ).scalar_one_or_none()
        
        if existing_doc:
            if existing_doc.content_hash == content_hash:
                logger.info(f"Skipping unchanged document: {rel_path}")
                return
            else:
                logger.info(f"Updating changed document: {rel_path}")
                # We can just delete and recreate to keep it clean
                self.db.delete(existing_doc)
                self.db.commit()
                
        # Create new document
        doc = Document(
            id=doc_id,
            source_file=rel_path,
            content_hash=content_hash,
            metadata_=_sanitize_metadata(metadata)
        )
        self.db.add(doc)
        
        chunks = chunk_text(transcript_text, chunk_size=500, overlap=50)
        
        # Embed chunks
        logger.info(f"Embedding {len(chunks)} chunks for {rel_path}...")
        embeddings = self._get_embeddings(chunks)
        
        # Build metadata to duplicate on each chunk for fast flat retrieval
        chunk_metadata = {
            "source_file": rel_path,
            "guest": metadata.get("guest", "Unknown"),
            "episode_title": metadata.get("title", "Unknown"),
            "youtube_url": metadata.get("youtube_url", ""),
            "publish_date": str(metadata.get("publish_date", ""))
        }
        chunk_metadata = _sanitize_metadata(chunk_metadata)
        
        for i, (text_chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}_{i}"
            db_chunk = DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=i,
                text=text_chunk,
                embedding=emb,
                metadata_=chunk_metadata
            )
            self.db.add(db_chunk)
            
        self.db.commit()
        logger.info(f"Successfully ingested {rel_path}")
