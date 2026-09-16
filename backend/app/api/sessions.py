from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.chat import (
    ChatSessionCreate, 
    ChatSessionResponse, 
    ChatSessionListResponse, 
    MessageCreate, 
    MessageResponse,
    AgentResponse
)
from app.services.chat_service import ChatService

router = APIRouter()

@router.post("/", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(session_in: ChatSessionCreate, db: Session = Depends(get_db)):
    service = ChatService(db)
    return service.create_session(session_in)

@router.get("/", response_model=List[ChatSessionListResponse])
def get_sessions(db: Session = Depends(get_db)):
    service = ChatService(db)
    return service.get_sessions()

@router.get("/{session_id}", response_model=ChatSessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    service = ChatService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: UUID, db: Session = Depends(get_db)):
    service = ChatService(db)
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

@router.post("/{session_id}/messages", response_model=AgentResponse)
def add_message(session_id: UUID, message_in: MessageCreate, db: Session = Depends(get_db)):
    service = ChatService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return service.add_message(session_id, message_in)
