from sqlalchemy.orm import Session
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatSessionCreate, MessageCreate
import uuid
import datetime
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_default_user(self) -> User:
        user = self.db.query(User).first()
        if not user:
            user = User()
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def create_session(self, session_in: ChatSessionCreate) -> ChatSession:
        user = self.get_or_create_default_user()
        new_session = ChatSession(
            title=session_in.title or "New Chat",
            user_id=user.id
        )
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    def get_sessions(self) -> List[ChatSession]:
        return self.db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()

    def get_session(self, session_id: uuid.UUID) -> Optional[ChatSession]:
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def delete_session(self, session_id: uuid.UUID) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def add_message(self, session_id: uuid.UUID, message_in: MessageCreate) -> dict:
        # 1. Save user message
        user_message = Message(
            session_id=session_id,
            role=message_in.role,
            content=message_in.content,
            meta=message_in.meta
        )
        self.db.add(user_message)

        session = self.get_session(session_id)
        if session:
            session.updated_at = datetime.datetime.utcnow()

        self.db.commit()
        self.db.refresh(user_message)

        # 2. Invoke Agent
        from app.services.agent_service import AgentService
        agent = AgentService(self.db)

        history = self.db.query(Message).filter(
            Message.session_id == session_id,
            Message.id != user_message.id
        ).order_by(Message.created_at.asc()).all()

        try:
            assistant_content, sources, skill_meta, artifact_data = agent.process_message(
                history, user_message.content
            )
        except Exception as e:
            logger.error(f"ChatService error in session {session_id}: {e}", exc_info=True)
            assistant_content = "I apologize, but I encountered an unexpected issue while processing your request. Please try again."
            sources = []
            skill_meta = None
            artifact_data = None

        # 3. Persist artifact if one was generated
        artifact_obj = None
        if artifact_data:
            from app.services.artifact_service import ArtifactService
            artifact_svc = ArtifactService(self.db)
            artifact_obj = artifact_svc.create(
                session_id=session_id,
                artifact_type=artifact_data["type"],
                title=artifact_data["title"],
                content=artifact_data["content"],
            )

        # 4. Build meta for the assistant message
        meta_data: dict = {}
        if sources:
            meta_data["sources"] = sources
        if skill_meta:
            meta_data.update(skill_meta)
        if artifact_obj:
            meta_data["artifact_id"] = str(artifact_obj.id)
        if not meta_data:
            meta_data = None

        # 5. Save assistant message
        assistant_message = Message(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            meta=meta_data
        )
        self.db.add(assistant_message)
        self.db.commit()
        self.db.refresh(assistant_message)

        # Link artifact to the assistant message now that we have its ID
        if artifact_obj:
            from app.services.artifact_service import ArtifactService
            ArtifactService(self.db).link_to_message(artifact_obj.id, assistant_message.id)

        return {
            "message": assistant_message,
            "provider": agent.get_provider_name(),
            "sources": sources,
            "artifact": artifact_obj,
        }
