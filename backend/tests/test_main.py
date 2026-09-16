import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_create_session():
    response = client.post("/api/sessions/", json={"title": "Test Chat"})
    assert response.status_code == 201
    assert response.json()["title"] == "Test Chat"
    assert "id" in response.json()

def test_get_sessions():
    client.post("/api/sessions/", json={"title": "S1"})
    client.post("/api/sessions/", json={"title": "S2"})
    response = client.get("/api/sessions/")
    assert response.status_code == 200
    assert len(response.json()) == 2

from unittest.mock import patch

def test_session_isolation_and_messages():
    s1 = client.post("/api/sessions/", json={"title": "S1"}).json()
    s2 = client.post("/api/sessions/", json={"title": "S2"}).json()

    with patch("app.services.agent_service.AgentService.process_message") as mock_process:
        mock_process.return_value = ("Hello back!", [], None)
        client.post(f"/api/sessions/{s1['id']}/messages", json={"role": "user", "content": "Hello in S1"})
        client.post(f"/api/sessions/{s2['id']}/messages", json={"role": "user", "content": "Hello in S2"})

    resp1 = client.get(f"/api/sessions/{s1['id']}")
    assert len(resp1.json()["messages"]) == 2
    assert resp1.json()["messages"][0]["content"] == "Hello in S1"

    resp2 = client.get(f"/api/sessions/{s2['id']}")
    assert len(resp2.json()["messages"]) == 2
    assert resp2.json()["messages"][0]["content"] == "Hello in S2"

def test_delete_session():
    s = client.post("/api/sessions/", json={"title": "Delete me"}).json()
    with patch("app.services.agent_service.AgentService.process_message") as mock_process:
        mock_process.return_value = ("Ack", [], None)
        client.post(f"/api/sessions/{s['id']}/messages", json={"role": "user", "content": "msg"})
    
    del_resp = client.delete(f"/api/sessions/{s['id']}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/sessions/{s['id']}")
    assert get_resp.status_code == 404
