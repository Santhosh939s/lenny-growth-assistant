import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SHIP30_SYSTEM_PROMPT = """You are an expert ghostwriter creating a "Ship 30 for 30" style essay.

Your task is to write a punchy, high-impact atomic essay (approximately 300-500 words) about the topic the user provides.
You must ground EVERY factual claim in the evidence supplied from Lenny's Podcast.

## Ship 30 Style Requirements
1. **Hook**: The first paragraph must be a punchy, memorable opening hook (2-4 sentences).
2. **Structure**: Write a flowing narrative. Use skimmable headings (## Heading), short paragraphs (1-3 sentences), bullet lists, and **bold emphasis** where useful.
3. **Depth**: Include practical, product/growth-oriented examples and an actionable takeaway section at the end.
4. **Length**: Aim for approximately 300-500 words. Do not pad with generic filler.

## Grounding Rules (Non-Negotiable)
- Every factual claim MUST be traceable to the provided evidence.
- Do NOT invent or fabricate direct quotations.
- Do NOT invent statistics, data, or numbers not present in the evidence.
- Do NOT invent episode titles, guest names, or URLs.
- If a claim cannot be supported by the evidence, omit it, or label it explicitly as "general reasoning" or "common practice" rather than attributing it to Lenny.
- The final article MUST NOT include a "Sources" section — that will be appended separately.

## Output Format
Your response must be valid Markdown.
The **very first line** of your response MUST be a Markdown H1 heading: `# Your Article Title Here`
"""

# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------

class Ship30Skill:
    """
    Independently reusable skill for generating Ship 30 for 30 style articles.

    The skill has no dependency on AgentService or any global state.
    It only needs:
      - a configured LLMProvider instance (from `app.services.llm`)
      - a topic string
      - a list of retrieved evidence chunks

    This makes the skill independently testable by supplying a mock provider.
    """

    def __init__(self, provider):
        """
        Args:
            provider: Any object that implements the LLMProvider interface,
                      i.e. has a `.chat(messages: list) -> dict` method.
        """
        self.provider = provider

    def generate_article(self, topic: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a Ship 30 for 30 article.

        Args:
            topic:  The article topic/request string.
            chunks: Structured evidence retrieved from RetrievalService.
                    Each chunk should contain: episode_title, guest, text, similarity,
                    and optionally youtube_url.

        Returns:
            {
              "type":       "ship30",
              "title":      str,
              "content":    str,   # Full Markdown article
              "word_count": int,   # Calculated from actual content, never hardcoded
              "sources":    list   # Deduplicated source citations
            }
        """
        # --- Build evidence block ---
        evidence_text = ""
        sources: List[Dict[str, Any]] = []

        for i, r in enumerate(chunks):
            source = {
                "title":       r.get("episode_title", "Unknown"),
                "guest":       r.get("guest", "Unknown"),
                "similarity":  r.get("similarity", 0.0),
                "youtube_url": r.get("youtube_url"),
            }
            if not any(s["title"] == source["title"] for s in sources):
                sources.append(source)

            # Limit evidence prompt to top 3 excerpts, 450 chars each, for fast CPU inference
            if i < 3:
                raw_text = (r.get("text") or "").strip()
                excerpt = raw_text[:450].strip() + ("..." if len(raw_text) > 450 else "")
                evidence_text += (
                    f"Episode Title: {r.get('episode_title', 'Unknown')}\n"
                    f"Guest: {r.get('guest', 'Unknown')}\n"
                    f"Excerpt: {excerpt}\n\n"
                )

        if not evidence_text.strip():
            evidence_text = (
                "No evidence found. You must explicitly state in the article that the "
                "available Lenny podcast material does not cover this specific topic."
            )

        system_prompt = SHIP30_SYSTEM_PROMPT + f"\n\n## Evidence from Lenny's Podcast\n{evidence_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Write a Ship 30 for 30 style article about: {topic}"},
        ]

        logger.info(f"Ship30Skill generating article for topic: '{topic}' with {len(sources)} sources.")

        # Pure generation call — no tools provided
        response = self.provider.chat(messages)
        content = response.get("content", "").strip()

        # --- Extract title from first H1 heading ---
        title = "Ship 30 for 30 Article"
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                raw_title = stripped[2:].strip()
                # Strip any residual markdown bold/italic markers
                title = re.sub(r"[*_]", "", raw_title).strip()
                break

        # --- Word count from actual generated content (never hardcoded) ---
        word_count = len(content.split())

        logger.info(f"Ship30Skill finished. word_count={word_count}, sources={len(sources)}")

        return {
            "type":       "ship30",
            "title":      title,
            "content":    content,
            "word_count": word_count,
            "sources":    sources,
        }
