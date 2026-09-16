from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ArtifactResponse(BaseModel):
    id: UUID
    session_id: UUID
    message_id: Optional[UUID] = None
    type: str         # "markdown" | "html"
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
