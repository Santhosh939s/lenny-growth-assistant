import uuid
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.artifact import Artifact

logger = logging.getLogger(__name__)


class ArtifactService:
    """Handles persistence and retrieval of generated artifacts."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        session_id: uuid.UUID,
        artifact_type: str,
        title: str,
        content: str,
        message_id: Optional[uuid.UUID] = None,
    ) -> Artifact:
        """Persist a new artifact and return the ORM object."""
        artifact = Artifact(
            session_id=session_id,
            message_id=message_id,
            type=artifact_type,
            title=title,
            content=content,
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        logger.info(f"Artifact created: id={artifact.id} type={artifact_type} title='{title}'")
        return artifact

    def get(self, artifact_id: uuid.UUID) -> Optional[Artifact]:
        """Retrieve a single artifact by ID."""
        return self.db.query(Artifact).filter(Artifact.id == artifact_id).first()

    def list_for_session(self, session_id: uuid.UUID) -> List[Artifact]:
        """List all artifacts for a session, newest first."""
        return (
            self.db.query(Artifact)
            .filter(Artifact.session_id == session_id)
            .order_by(Artifact.created_at.desc())
            .all()
        )

    def link_to_message(self, artifact_id: uuid.UUID, message_id: uuid.UUID) -> None:
        """Associate an artifact with the message that generated it."""
        artifact = self.get(artifact_id)
        if artifact:
            artifact.message_id = message_id
            artifact.updated_at = datetime.utcnow()
            self.db.commit()
