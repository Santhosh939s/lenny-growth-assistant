from typing import Any, Dict, List
from sqlalchemy import String, Integer, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", 
        back_populates="document", 
        cascade="all, delete-orphan"
    )

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
