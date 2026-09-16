"""
Independent unit tests for Ship30Skill.

All LLM calls are mocked — no Ollama or Anthropic credentials needed.
"""
import pytest
from unittest.mock import MagicMock
from app.services.skills.ship30 import Ship30Skill


SAMPLE_CHUNKS = [
    {
        "episode_title": "How to build a great product",
        "guest": "Shreyas Doshi",
        "text": "Prioritization is about saying no to good ideas so you can focus on great ones.",
        "similarity": 0.92,
        "youtube_url": "https://www.youtube.com/watch?v=abc123",
    },
    {
        "episode_title": "Product strategy that works",
        "guest": "Gibson Biddle",
        "text": "A strategy must be both inspiring and concrete.",
        "similarity": 0.87,
        "youtube_url": None,
    },
]

SAMPLE_ARTICLE_CONTENT = """# The Art of Saying No: How Product Teams Should Prioritize

Most product teams are drowning in good ideas. The problem isn't imagination—it's judgment.

## Why Prioritization Fails

**The real enemy of great products is mediocrity disguised as progress.**
Teams ship feature after feature without asking: does this actually matter?

According to insights from Lenny's podcast, prioritization is about saying no to good ideas so you can focus on great ones.

## A Framework That Works

A product strategy must be both inspiring and concrete. Without the concrete part, nothing gets built.

- Anchor everything to a clear user outcome
- Be explicit about what you're NOT building
- Revisit priorities at least monthly

## The Hidden Cost of Yes

Every yes is a no in disguise. When you add a feature, you commit engineering time, design bandwidth, and ongoing maintenance.

**Choose deliberately. Ship fewer things. Make them matter.**

## Actionable Takeaway

Run a "kill meeting" once a quarter. List every project on your roadmap and vote on which ones to cut. You'll be surprised how many no-brainers emerge.

The best product teams aren't the ones who build the most. They're the ones who build the right things.
"""


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat.return_value = {"content": SAMPLE_ARTICLE_CONTENT}
    return provider


@pytest.fixture
def skill(mock_provider):
    return Ship30Skill(mock_provider)


# ---------------------------------------------------------------------------
# Independent invocation
# ---------------------------------------------------------------------------

def test_ship30_skill_is_independently_invocable(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    assert result is not None
    assert "type" in result


def test_ship30_skill_receives_evidence(skill, mock_provider):
    skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Provider must be called with messages that include the evidence
    call_args = mock_provider.chat.call_args
    messages = call_args[0][0]
    system_msg = messages[0]["content"]
    assert "Shreyas Doshi" in system_msg
    assert "Gibson Biddle" in system_msg


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_ship30_returns_structured_dict(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    assert result["type"] == "ship30"
    assert "title" in result
    assert "content" in result
    assert "word_count" in result
    assert "sources" in result


def test_ship30_word_count_is_from_actual_content(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Word count must match actual content, never hardcoded to 1250
    actual_count = len(result["content"].split())
    assert result["word_count"] == actual_count


def test_ship30_content_has_h1_title(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Content must start with an H1 heading
    lines = result["content"].splitlines()
    h1_lines = [l for l in lines if l.strip().startswith("# ")]
    assert len(h1_lines) >= 1, "Article must contain at least one H1 heading"


def test_ship30_title_extracted_from_content(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Title should be extracted from the first H1, not a fallback
    assert result["title"] == "The Art of Saying No: How Product Teams Should Prioritize"


def test_ship30_content_has_headings(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Must have at least one ## subheading
    assert "## " in result["content"]


def test_ship30_content_has_bullets(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Must have at least one bullet
    assert "- " in result["content"] or "* " in result["content"]


def test_ship30_content_has_bold(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    # Must have bold text
    assert "**" in result["content"]


# ---------------------------------------------------------------------------
# Sources are preserved
# ---------------------------------------------------------------------------

def test_ship30_sources_are_preserved(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    titles = [s["title"] for s in result["sources"]]
    assert "How to build a great product" in titles
    assert "Product strategy that works" in titles


def test_ship30_sources_are_deduplicated(skill):
    # Duplicate chunks should produce only 1 source entry
    duplicate_chunks = SAMPLE_CHUNKS + [SAMPLE_CHUNKS[0]]
    result = skill.generate_article("product prioritization", duplicate_chunks)
    titles = [s["title"] for s in result["sources"]]
    assert titles.count("How to build a great product") == 1


def test_ship30_sources_include_youtube_url(skill):
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    src = next(s for s in result["sources"] if s["title"] == "How to build a great product")
    assert src["youtube_url"] == "https://www.youtube.com/watch?v=abc123"


# ---------------------------------------------------------------------------
# Edge case — empty evidence
# ---------------------------------------------------------------------------

def test_ship30_handles_empty_evidence(mock_provider):
    mock_provider.chat.return_value = {
        "content": "# No Evidence Found\n\nThe available Lenny podcast material does not cover this topic."
    }
    skill = Ship30Skill(mock_provider)
    result = skill.generate_article("obscure topic", [])
    assert result["type"] == "ship30"
    assert result["sources"] == []
    assert result["word_count"] == len(result["content"].split())


# ---------------------------------------------------------------------------
# Fabricated citations check — sources list integrity
# ---------------------------------------------------------------------------

def test_ship30_does_not_add_unlisted_sources(skill):
    """Sources list must only contain entries from the provided chunks."""
    result = skill.generate_article("product prioritization", SAMPLE_CHUNKS)
    valid_titles = {c["episode_title"] for c in SAMPLE_CHUNKS}
    for s in result["sources"]:
        assert s["title"] in valid_titles, (
            f"Source '{s['title']}' was not in the provided chunks — potential fabrication."
        )
