from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID
from app.schemas.artifact import ArtifactResponse

class MessageBase(BaseModel):
    role: str
    content: str
    meta: Optional[Any] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: UUID
    session_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class SourceCitation(BaseModel):
    title: str
    guest: str
    similarity: float

class AgentResponse(BaseModel):
    message: MessageResponse
    provider: str
    sources: List[SourceCitation] = []
    artifact: Optional[ArtifactResponse] = None

class ChatSessionBase(BaseModel):
    title: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionResponse(ChatSessionBase):
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

class ChatSessionListResponse(ChatSessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
