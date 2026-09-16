from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.document import Document, DocumentChunk
from app.config import settings

router = APIRouter()

@router.get("/stats")
def get_knowledge_stats(db: Session = Depends(get_db)):
    doc_count = db.query(func.count(Document.id)).scalar()
    chunk_count = db.query(func.count(DocumentChunk.id)).scalar()
    
    return {
        "documents": doc_count,
        "chunks": chunk_count,
        "embedding_model": settings.OLLAMA_EMBED_MODEL
    }
