import logging
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.services.llm.factory import get_llm_provider
from app.services.retrieval_service import RetrievalService
from app.services.skills.ship30 import Ship30Skill
from app.services.skills.artifact_skill import ArtifactSkill
from app.models.message import Message
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Lenny Growth Assistant. Your job is to help users with questions and writing tasks using Lenny's Podcast knowledge base.

You have two search and writing tools available:

1. `search_lenny_knowledge` — Use this to answer FACTUAL questions about Lenny's podcast content.
   Invoke when the user asks what Lenny says about X, questions about product/growth topics, etc.

2. `write_ship30_article` — Use this ONLY when the user EXPLICITLY asks you to write a Ship 30 for 30 style article.

Do NOT invoke tools for conversational messages like "Hi", "Thanks", etc.
When answering with search results, cite the guest or episode from the evidence.
Always complete your sentences and thoughts fully. Provide structured, actionable answers (2-3 short sections or bullet points with clear takeaways).
Keep your tone helpful, professional, and slightly informal."""

# ---------------------------------------------------------------------------
# Tool Definitions (for capable models)
# ---------------------------------------------------------------------------

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_lenny_knowledge",
        "description": "Search Lenny's Podcast transcripts for relevant information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"]
        }
    }
}

SHIP30_TOOL = {
    "type": "function",
    "function": {
        "name": "write_ship30_article",
        "description": "Generate a Ship 30 for 30 style article grounded in Lenny's Podcast. Invoke ONLY for explicit Ship30/article writing requests.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The article topic."}
            },
            "required": ["topic"]
        }
    }
}

ALL_TOOLS = [SEARCH_TOOL, SHIP30_TOOL]

# ---------------------------------------------------------------------------
# Deterministic intent detectors
# ---------------------------------------------------------------------------

_SHIP30_PATTERNS = re.compile(
    r'\b(ship\s*30|write\s+(a\s+)?(ship|article|essay|post|piece)|'
    r'turn\s+.{0,40}\s+into\s+(a\s+)?(article|post|essay)|'
    r'write\s+me\s+(a\s+)?(article|essay|post))\b',
    re.IGNORECASE
)

_MARKDOWN_ARTIFACT_PATTERNS = re.compile(
    r'\b((create|build|generate|make)\s+(a\s+)?(\w+\s+)?(markdown|md)\b'
    r'|(create|build|generate|make|write)\s+(a\s+)?(\w+\s+)?(product\s+brief|strategy\s+doc|document|checklist|spec|roadmap|one[\s-]pager)\b'
    r'|turn\s+.{0,50}\s+into\s+(a\s+)?(brief|document|checklist|spec)\b'
    r'|markdown\s+artifact\b)',
    re.IGNORECASE
)

_HTML_ARTIFACT_PATTERNS = re.compile(
    r'\b((create|build|generate|make)\s+(a\s+)?(\w+\s+)?(html|landing\s+page|web\s+page|webpage|pricing\s+card|dashboard|widget)\b'
    r'|html\s+artifact\b)',
    re.IGNORECASE
)


def _is_ship30_request(text: str) -> bool:
    is_art, _ = _is_artifact_request(text)
    return bool(_SHIP30_PATTERNS.search(text)) and not is_art


def _is_artifact_request(text: str) -> Tuple[bool, str]:
    """Returns (is_artifact, artifact_type)."""
    if _HTML_ARTIFACT_PATTERNS.search(text):
        return True, "html"
    if _MARKDOWN_ARTIFACT_PATTERNS.search(text):
        return True, "markdown"
    return False, ""


def _is_conversational(text: str) -> bool:
    stripped = text.strip().lower()
    if len(stripped) <= 10:
        return True
    return stripped in {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay"}


def _extract_topic(text: str) -> str:
    """Strip request prefix from text to get the core topic."""
    topic = re.sub(
        r'^(create\s+(a\s+)?(markdown\s+|html\s+|md\s+)?(document|brief|checklist|spec|landing\s+page|page|artifact)?\s*(about|for|on)?'
        r'|write\s+(me\s+)?(a\s+)?(ship\s*30\s*(for\s*30\s*)?(style\s+)?(article|essay|post)?(\s+about)?|article|essay|post)\s*(about)?'
        r'|turn\s+.{0,40}\s+into\s+(a\s+)?(article|post|essay|brief|document|checklist)'
        r'|make\s+(a\s+)?(markdown\s+)?(checklist|document|brief|spec)\s*(about|for|on)?'
        r'|generate\s+(a\s+)?(document|brief|spec|checklist)\s*(about|for|on)?'
        r'|build\s+(a\s+)?(html|landing\s+page|web\s+page)\s*(about|for)?)',
        '', text, flags=re.IGNORECASE
    ).strip().rstrip('.,;:!?') or text
    return topic


# ---------------------------------------------------------------------------
class ResilientProviderProxy:
    def __init__(self, agent_service: "AgentService"):
        self._agent = agent_service

    @property
    def provider_name(self) -> str:
        return self._agent.get_provider_name()

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return self._agent._chat_with_provider(messages, tools=tools)


# ---------------------------------------------------------------------------
# AgentService
# ---------------------------------------------------------------------------

class AgentService:
    def __init__(self, db: Session):
        self.db = db
        self.provider = get_llm_provider()
        self._active_provider_name = self.provider.provider_name
        self.retrieval_service = RetrievalService(db)

        # Automatic fallback to Claude if Ollama encounters a problem
        self.fallback_provider = None
        if settings.ANTHROPIC_API_KEY and settings.MODEL_PROVIDER.lower() == "ollama":
            try:
                from app.services.llm.anthropic_provider import AnthropicProvider
                self.fallback_provider = AnthropicProvider()
                logger.info("Claude (Anthropic) configured as automatic fallback provider.")
            except Exception as e:
                logger.warning(f"Could not configure fallback provider: {e}")

        # Skills use the proxy so their generation calls also automatically fall back to Claude if Ollama fails
        proxy = ResilientProviderProxy(self)
        self.ship30_skill = Ship30Skill(proxy)
        self.artifact_skill = ArtifactSkill(proxy)

    def _chat_with_provider(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call primary provider (Ollama). Fall back to Claude if it fails or times out."""
        try:
            res = self.provider.chat(messages, tools=tools)
            self._active_provider_name = self.provider.provider_name
            return res
        except Exception as primary_err:
            if self.fallback_provider:
                logger.warning(
                    f"Primary provider {self.provider.provider_name} failed: {primary_err}. "
                    f"Automatically falling back to {self.fallback_provider.provider_name}."
                )
                try:
                    res = self.fallback_provider.chat(messages, tools=tools)
                    self._active_provider_name = self.fallback_provider.provider_name
                    return res
                except Exception as fallback_err:
                    logger.error(f"Fallback provider also failed: {fallback_err}")
                    raise fallback_err
            raise primary_err

    def _build_messages(self, history: List[Message], current_content: str) -> List[Dict[str, Any]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Keep last 6 messages to keep prompt small and inference fast on CPU
        recent_history = history[-6:] if len(history) > 6 else history
        for msg in recent_history:
            if msg.role not in ("user", "assistant"):
                continue
            messages.append({"role": msg.role, "content": msg.content or ""})
        messages.append({"role": "user", "content": current_content})
        return messages

    def get_provider_name(self) -> str:
        return getattr(self, "_active_provider_name", self.provider.provider_name)

    def _format_chunks_for_llm(self, chunks: List[Dict]) -> str:
        text = ""
        for r in chunks:
            raw_text = (r.get('text') or '').strip()
            # Excerpt to 400 chars to avoid prompt token bloat on CPU
            excerpt = raw_text[:400].strip() + ("..." if len(raw_text) > 400 else "")
            text += f"Episode: {r.get('episode_title')}\nGuest: {r.get('guest')}\nExcerpt: {excerpt}\n\n"
        return text or "No results found."

    def _extract_sources(self, chunks: List[Dict], existing: List[Dict]) -> List[Dict]:
        for r in chunks:
            source = {
                "title":       r.get("episode_title", "Unknown"),
                "guest":       r.get("guest", "Unknown"),
                "similarity":  r.get("similarity", 0.0),
                "youtube_url": r.get("youtube_url"),
            }
            if not any(s["title"] == source["title"] for s in existing):
                existing.append(source)
        return existing

    def _invoke_ship30(self, topic: str) -> Tuple[str, List[Dict], Optional[Dict], Optional[Dict]]:
        logger.info(f"Invoking Ship30Skill for topic: '{topic}'")
        chunks = self.retrieval_service.retrieve(topic, top_k=5)
        sources = self._extract_sources(chunks, [])
        article = self.ship30_skill.generate_article(topic, chunks)
        sources = article.get("sources", sources)
        meta = {
            "type": article["type"],
            "title": article["title"],
            "word_count": article["word_count"],
            "sources": article["sources"],
        }
        return article["content"], sources, meta, None

    def _invoke_artifact(
        self, topic: str, artifact_type: str, needs_retrieval: bool
    ) -> Tuple[str, List[Dict], Optional[Dict], Optional[Dict]]:
        logger.info(f"Invoking ArtifactSkill: type={artifact_type} topic='{topic}'")
        chunks: List[Dict] = []
        sources: List[Dict] = []

        if needs_retrieval:
            chunks = self.retrieval_service.retrieve(topic, top_k=5)
            sources = self._extract_sources(chunks, [])

        artifact_data = self.artifact_skill.generate(topic, artifact_type, chunks)

        # The assistant message content is a short confirmation
        content = f"I've created a **{artifact_type}** artifact: **{artifact_data['title']}**"
        if sources:
            content += "\n\nGrounded in the following Lenny episodes:"
            for s in sources:
                content += f"\n- {s['title']} (Guest: {s['guest']})"

        meta = {"artifact_type": artifact_type, "artifact_title": artifact_data["title"]}

        return content, sources, meta, artifact_data

    def _invoke_search(
        self, query: str, messages: List[Dict], tool_call: Optional[Dict] = None
    ) -> Tuple[str, List[Dict], Optional[Dict], Optional[Dict]]:
        logger.info(f"Invoking RetrievalService for query: '{query}'")
        chunks = self.retrieval_service.retrieve(query, top_k=3)
        sources = self._extract_sources(chunks, [])
        tool_text = self._format_chunks_for_llm(chunks)

        synthesis_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {query}\n\n"
                    f"Evidence from Lenny's Podcast episodes:\n{tool_text}\n\n"
                    f"Please synthesize a clear, actionable answer to the question using the evidence provided above. Complete your thoughts and cite the guest or episode."
                )
            }
        ]

        try:
            final = self._chat_with_provider(synthesis_messages)
            return final.get("content", ""), sources, None, None
        except Exception as e:
            logger.error(f"Failed to generate answer from evidence: {e}", exc_info=True)
            return "I gathered the relevant episodes from Lenny's knowledge base, but had an issue synthesizing the answer. Please try again.", sources, None, None

    def process_message(
        self, history: List[Message], current_content: str
    ) -> Tuple[str, List[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Process the user message. Returns (content, sources, meta, artifact_data).

        artifact_data is None for normal answers; contains {type, title, content} for artifact generation.

        Routing priority:
        1. HTML artifact keyword → ArtifactSkill (html), no retrieval needed
        2. Markdown artifact keyword → ArtifactSkill (markdown), with Lenny retrieval
        3. Ship30 keyword → Ship30Skill, with Lenny retrieval
        4. LLM native tool call → search or ship30
        5. Fallback: no tool call → retrieval injection or direct response
        """
        messages = self._build_messages(history, current_content)
        logger.info(f"Agent processing via {self.provider.provider_name}")

        # ------------------------------------------------------------------ #
        # Priority 1 & 2: Deterministic artifact detection                    #
        # ------------------------------------------------------------------ #
        is_artifact, artifact_type = _is_artifact_request(current_content)
        if is_artifact:
            topic = _extract_topic(current_content)
            # HTML artifacts are typically visual — don't force Lenny retrieval unless the user
            # mentions Lenny-grounded content explicitly
            needs_retrieval = artifact_type == "markdown" or "lenny" in current_content.lower()
            logger.info(f"Deterministic artifact match: type={artifact_type}, retrieval={needs_retrieval}")
            return self._invoke_artifact(topic, artifact_type, needs_retrieval)

        # ------------------------------------------------------------------ #
        # Priority 3: Ship30 keyword                                          #
        # ------------------------------------------------------------------ #
        if _is_ship30_request(current_content):
            topic = _extract_topic(current_content)
            logger.info(f"Deterministic Ship30 keyword match.")
            return self._invoke_ship30(topic)

        # ------------------------------------------------------------------ #
        # Priority 4: LLM native tool call                                    #
        # ------------------------------------------------------------------ #
        try:
            response = self._chat_with_provider(messages, tools=ALL_TOOLS)
        except Exception as e:
            logger.error(f"LLM call with tools failed: {e}. Retrying without tools.")
            try:
                response = self._chat_with_provider(messages)
            except Exception as e2:
                logger.error(f"LLM call failed: {e2}", exc_info=True)
                return "I apologize, but I encountered an issue communicating with the AI service. Please ensure the model service is running and try again.", [], None, None

        tool_calls = response.get("tool_calls") or []

        if tool_calls:
            tool_call = tool_calls[0]
            tool_name = tool_call.get("name", "")
            try:
                args = tool_call.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)

                if tool_name == "write_ship30_article":
                    topic = args.get("topic", current_content)
                    return self._invoke_ship30(topic)

                elif tool_name == "search_lenny_knowledge":
                    query = args.get("query", current_content)
                    return self._invoke_search(query, messages, tool_call=tool_call)

            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                return "I encountered a problem while retrieving information to answer your request. Please try again.", [], None, None

        # ------------------------------------------------------------------ #
        # Priority 5: Fallback — no native tool call                          #
        # ------------------------------------------------------------------ #
        if not _is_conversational(current_content):
            logger.info("No native tool call. Running fallback retrieval.")
            try:
                chunks = self.retrieval_service.retrieve(current_content, top_k=3)
                if chunks and any(r.get("similarity", 0) > 0.6 for r in chunks):
                    return self._invoke_search(current_content, messages, tool_call=None)
            except Exception as e:
                logger.error(f"Fallback retrieval error: {e}")

        return response.get("content", ""), [], None, None
