import pytest
import uuid
import re
from unittest.mock import MagicMock
from app.services.skills.artifact_skill import ArtifactSkill
from app.services.artifact_service import ArtifactService
from app.models.artifact import Artifact
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user import User


# ---------------------------------------------------------------------------
# ArtifactSkill Unit Tests
# ---------------------------------------------------------------------------

def test_artifact_skill_unsupported_type():
    provider = MagicMock()
    skill = ArtifactSkill(provider)
    with pytest.raises(ValueError, match="Unsupported artifact type"):
        skill.generate("my topic", "unsupported_type")


def test_artifact_skill_generate_markdown():
    provider = MagicMock()
    provider.chat.return_value = {
        "content": "# Product Prioritization Guide\n\n## Overview\nPrioritizing features requires discipline.\n\n- Impact\n- Effort"
    }
    skill = ArtifactSkill(provider)
    res = skill.generate("Product Prioritization Guide", "markdown", chunks=[
        {"episode_title": "Ep 1", "guest": "Shreyas", "text": "Prioritization framework"}
    ])

    assert res["type"] == "markdown"
    assert res["title"] == "Product Prioritization Guide"
    assert "# Product Prioritization Guide" in res["content"]
    assert provider.chat.called


def test_artifact_skill_generate_html_with_csp():
    provider = MagicMock()
    raw_html = """<!DOCTYPE html>
<html>
<head>
    <title>Customer Funnel Dashboard</title>
    <style>body { font-family: sans-serif; }</style>
</head>
<body>
    <h1>Dashboard</h1>
    <div class="card">Conversion: 4.2%</div>
</body>
</html>"""
    provider.chat.return_value = {"content": raw_html}
    skill = ArtifactSkill(provider)
    res = skill.generate("Customer Funnel Dashboard", "html")

    assert res["type"] == "html"
    assert res["title"] == "Customer Funnel Dashboard"
    content = res["content"]

    # Verify CSP is present
    assert '<meta http-equiv="Content-Security-Policy"' in content
    # Verify strict directives
    assert "default-src 'none'" in content
    assert "style-src 'unsafe-inline'" in content
    assert "img-src data:" in content
    assert "font-src data:" in content
    assert "connect-src 'none'" in content
    assert "form-action 'none'" in content
    assert "base-uri 'none'" in content
    assert "script-src 'none'" in content


def test_inject_csp_meta_head_injection():
    html_without_head = "<div><p>Simple snippet</p></div>"
    injected = ArtifactSkill.inject_csp(html_without_head, allow_scripts=False)
    assert '<meta http-equiv="Content-Security-Policy"' in injected
    assert "connect-src 'none'" in injected
    assert "script-src 'none'" in injected


def test_inject_csp_replaces_existing_csp():
    html_with_weak_csp = """<html>
<head>
    <meta http-equiv="Content-Security-Policy" content="default-src *;">
</head>
<body><h1>Hello</h1></body>
</html>"""
    injected = ArtifactSkill.inject_csp(html_with_weak_csp, allow_scripts=False)
    # Weak CSP must be replaced
    assert "default-src *" not in injected
    assert "connect-src 'none'" in injected
    assert "script-src 'none'" in injected


# ---------------------------------------------------------------------------
# ArtifactService Database Unit Tests
# ---------------------------------------------------------------------------

def test_artifact_service_crud():
    mock_db = MagicMock()
    service = ArtifactService(mock_db)
    session_id = uuid.uuid4()
    msg_id = uuid.uuid4()

    # 1. Create
    artifact = service.create(
        session_id=session_id,
        artifact_type="markdown",
        title="Test Doc",
        content="# Test Doc Content",
        message_id=msg_id
    )
    assert mock_db.add.called
    assert mock_db.commit.called
    assert artifact.session_id == session_id
    assert artifact.type == "markdown"
    assert artifact.title == "Test Doc"

    # 2. Get
    mock_db.query.return_value.filter.return_value.first.return_value = artifact
    fetched = service.get(artifact.id)
    assert fetched == artifact

    # 3. List for session
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [artifact]
    items = service.list_for_session(session_id)
    assert len(items) == 1
    assert items[0] == artifact

    # 4. Link to message
    new_msg_id = uuid.uuid4()
    service.link_to_message(artifact.id, new_msg_id)
    assert artifact.message_id == new_msg_id
