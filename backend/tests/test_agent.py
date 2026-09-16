import pytest
from unittest.mock import MagicMock, patch
from app.services.agent_service import AgentService
from app.models.message import Message
import uuid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_retrieval_service():
    with patch("app.services.agent_service.RetrievalService") as mock:
        yield mock


@pytest.fixture
def mock_provider():
    with patch("app.services.agent_service.get_llm_provider") as mock:
        yield mock


@pytest.fixture
def mock_ship30_skill():
    with patch("app.services.agent_service.Ship30Skill") as mock:
        yield mock


# ---------------------------------------------------------------------------
# AgentService initialization
# ---------------------------------------------------------------------------

def test_agent_initialization(mock_db, mock_provider, mock_retrieval_service, mock_ship30_skill):
    agent = AgentService(mock_db)
    assert agent.provider is not None
    assert agent.retrieval_service is not None
    assert agent.ship30_skill is not None


# ---------------------------------------------------------------------------
# Normal conversational answer — no tool calls
# ---------------------------------------------------------------------------

def test_agent_process_message_no_tools(mock_db, mock_provider, mock_retrieval_service, mock_ship30_skill):
    mock_instance = mock_provider.return_value
    mock_instance.chat.return_value = {
        "content": "This is a simple answer.",
        "tool_calls": []
    }
    # Make retrieval return nothing relevant so fallback doesn't fire
    mock_retrieval_service.return_value.retrieve.return_value = []

    agent = AgentService(mock_db)
    content, sources, meta, artifact_data = agent.process_message([], "Hi there!")

    assert content == "This is a simple answer."
    assert sources == []
    assert meta is None
    assert artifact_data is None
    mock_instance.chat.assert_called_once()


# ---------------------------------------------------------------------------
# RAG — search_lenny_knowledge tool call
# ---------------------------------------------------------------------------

def test_agent_process_message_with_search_tool(mock_db, mock_provider, mock_retrieval_service, mock_ship30_skill):
    mock_instance = mock_provider.return_value
    mock_instance.chat.side_effect = [
        {
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "name": "search_lenny_knowledge",
                "arguments": {"query": "product market fit"}
            }]
        },
        {
            "content": "Based on Lenny, PMF is crucial.",
            "tool_calls": []
        }
    ]

    mock_retrieval_instance = mock_retrieval_service.return_value
    mock_retrieval_instance.retrieve.return_value = [
        {"episode_title": "PMF Episode", "guest": "Marc", "text": "PMF is great.", "similarity": 0.9}
    ]

    agent = AgentService(mock_db)
    content, sources, meta, artifact_data = agent.process_message([], "What is PMF?")

    assert content == "Based on Lenny, PMF is crucial."
    assert len(sources) == 1
    assert sources[0]["title"] == "PMF Episode"
    assert sources[0]["guest"] == "Marc"
    assert meta is None  # Normal search, no ship30 meta
    assert artifact_data is None
    assert mock_instance.chat.call_count == 2
    mock_retrieval_instance.retrieve.assert_called_once_with("product market fit", top_k=3)


# ---------------------------------------------------------------------------
# Ship 30 — write_ship30_article tool call
# ---------------------------------------------------------------------------

def test_agent_invokes_ship30_on_article_request(mock_db, mock_provider, mock_retrieval_service, mock_ship30_skill):
    mock_instance = mock_provider.return_value
    mock_instance.chat.return_value = {
        "content": "",
        "tool_calls": [{
            "id": "call_2",
            "name": "write_ship30_article",
            "arguments": {"topic": "product-led growth"}
        }]
    }

    mock_retrieval_instance = mock_retrieval_service.return_value
    mock_retrieval_instance.retrieve.return_value = [
        {"episode_title": "PLG Episode", "guest": "Elena", "text": "PLG drives growth.", "similarity": 0.88}
    ]

    mock_skill_instance = mock_ship30_skill.return_value
    mock_skill_instance.generate_article.return_value = {
        "type": "ship30",
        "title": "How Product-Led Growth Changes Everything",
        "content": "# How Product-Led Growth Changes Everything\n\nHook.\n\n## Section\n\nBody.",
        "word_count": 12,
        "sources": [{"title": "PLG Episode", "guest": "Elena", "similarity": 0.88, "youtube_url": None}]
    }

    agent = AgentService(mock_db)
    content, sources, meta, artifact_data = agent.process_message([], "Write a Ship 30 article about product-led growth.")

    # Content is the article markdown
    assert "How Product-Led Growth Changes Everything" in content
    # Sources are preserved
    assert len(sources) == 1
    assert sources[0]["title"] == "PLG Episode"
    # Meta is set and structured
    assert meta is not None
    assert meta["type"] == "ship30"
    assert meta["title"] == "How Product-Led Growth Changes Everything"
    assert meta["word_count"] == 12
    assert artifact_data is None
    # Ship30Skill.generate_article was called with topic and chunks
    mock_skill_instance.generate_article.assert_called_once()
    call_args = mock_skill_instance.generate_article.call_args
    actual_topic = call_args[0][0]  # topic
    # Topic should contain the subject, allowing for minor extraction differences
    assert "product-led growth" in actual_topic.lower()  # topic
    # retrieval was called with top_k=5 for ship30
    mock_retrieval_instance.retrieve.assert_called_once()
    retrieve_call = mock_retrieval_instance.retrieve.call_args
    assert retrieve_call[1].get("top_k") == 5 or retrieve_call[0][1] == 5


# ---------------------------------------------------------------------------
# Normal question does NOT invoke Ship30
# ---------------------------------------------------------------------------

def test_normal_question_does_not_invoke_ship30(mock_db, mock_provider, mock_retrieval_service, mock_ship30_skill):
    mock_instance = mock_provider.return_value
    mock_instance.chat.side_effect = [
        {
            "content": "",
            "tool_calls": [{
                "id": "call_3",
                "name": "search_lenny_knowledge",
                "arguments": {"query": "onboarding best practices"}
            }]
        },
        {
            "content": "Onboarding should be simple.",
            "tool_calls": []
        }
    ]
    mock_retrieval_service.return_value.retrieve.return_value = [
        {"episode_title": "Onboarding Ep", "guest": "Jane", "text": "Keep it simple.", "similarity": 0.85}
    ]

    agent = AgentService(mock_db)
    content, sources, meta, artifact_data = agent.process_message([], "What did Lenny's guests say about onboarding?")

    # Ship30Skill should NEVER be called
    mock_ship30_skill.return_value.generate_article.assert_not_called()
    assert meta is None
    assert artifact_data is None
    assert content == "Onboarding should be simple."
