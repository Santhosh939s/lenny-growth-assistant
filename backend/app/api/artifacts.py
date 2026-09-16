from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.schemas.artifact import ArtifactResponse
from app.services.artifact_service import ArtifactService

router = APIRouter()


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: UUID, db: Session = Depends(get_db)):
    svc = ArtifactService(db)
    artifact = svc.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.get("/session/{session_id}", response_model=List[ArtifactResponse])
def list_artifacts_for_session(session_id: UUID, db: Session = Depends(get_db)):
    svc = ArtifactService(db)
    return svc.list_for_session(session_id)
