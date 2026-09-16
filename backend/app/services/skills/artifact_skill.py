import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

MARKDOWN_SYSTEM_PROMPT = """You are an expert technical writer creating a polished Markdown document.

Generate a well-structured Markdown document on the topic the user requests.
You MUST ground all factual claims in the provided evidence from Lenny's Podcast.

## Formatting Requirements
- Use `#` for the document title (first line)
- Use `##` for major sections
- Use `###` for subsections where appropriate
- Short paragraphs (2-4 sentences)
- Use bullet lists, numbered lists, **bold**, and *italic* where it improves clarity
- Include a clear, actionable summary or conclusion
- Target a concise, high-value document (approximately 200-350 words)

## Grounding Rules
- EVERY factual claim must be traceable to the provided evidence
- Do NOT invent quotes, statistics, episode titles, or guests
- If something cannot be supported by the evidence, omit it or label it as general guidance

## Output
Return ONLY the Markdown document. No preamble, no apology, no commentary.
The very first line MUST be a Markdown H1: `# Document Title`
"""

HTML_SYSTEM_PROMPT = """You are an expert frontend developer creating a self-contained HTML/CSS document.

Generate clean, modern HTML with embedded CSS for the visual artifact the user requests.

## Requirements
- A complete, self-contained HTML document (includes <!DOCTYPE html>, <head>, <body>)
- Modern, attractive CSS styling embedded in a <style> tag in the <head>
- Responsive design (works on different screen widths)
- Professional color scheme and typography

## STRICT SECURITY RULES — You MUST follow these:
- Do NOT include any <script> tags
- Do NOT include any inline event handlers (onclick, onmouseover, onload, etc.)
- Do NOT include any javascript: URLs in href or src attributes
- Do NOT include <form> tags that POST to external URLs
- Do NOT include <iframe>, <object>, <embed> tags
- Do NOT include any external resource URLs (no CDN links, no external fonts via @import from external domains)
- Do NOT include any meta refresh or redirect tags
- All styling MUST use static CSS only — no dynamic CSS variables that reference JavaScript

## Output
Return ONLY the complete HTML document. No preamble, no apology, no commentary.
Start with <!DOCTYPE html>.
"""


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------

class ArtifactSkill:
    """
    Independently reusable skill for generating Markdown or HTML artifacts.

    Takes a configured LLMProvider and produces a structured artifact dict.
    Has no dependency on AgentService or global application state.
    Fully independently testable by supplying a mock provider.
    """

    ALLOWED_TYPES = {"markdown", "html"}

    def __init__(self, provider):
        """
        Args:
            provider: Any object implementing the LLMProvider interface
                      (has a `.chat(messages) -> dict` method).
        """
        self.provider = provider

    def generate(
        self,
        topic: str,
        artifact_type: str,
        chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an artifact of the specified type.

        Args:
            topic:         The user's request / topic string.
            artifact_type: "markdown" or "html"
            chunks:        Retrieved evidence (Lenny RAG results). May be empty for HTML visual artifacts.

        Returns:
            {
              "type":    "markdown" | "html",
              "title":   str,
              "content": str,
            }
        """
        if artifact_type not in self.ALLOWED_TYPES:
            raise ValueError(f"Unsupported artifact type: {artifact_type!r}. Must be one of {self.ALLOWED_TYPES}")

        chunks = chunks or []

        if artifact_type == "markdown":
            return self._generate_markdown(topic, chunks)
        else:
            return self._generate_html(topic, chunks)

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def _generate_markdown(self, topic: str, chunks: List[Dict]) -> Dict[str, Any]:
        evidence_text = self._build_evidence_block(chunks)
        system_prompt = MARKDOWN_SYSTEM_PROMPT + f"\n\n## Evidence from Lenny's Podcast\n{evidence_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a Markdown document about: {topic}"},
        ]

        logger.info(f"ArtifactSkill generating markdown for: '{topic}' with {len(chunks)} evidence chunks")
        response = self.provider.chat(messages)
        content = response.get("content", "").strip()

        title = self._extract_title(content, fallback=f"Document: {topic[:60]}")
        logger.info(f"ArtifactSkill markdown done. title='{title}' chars={len(content)}")

        return {"type": "markdown", "title": title, "content": content}

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    def _generate_html(self, topic: str, chunks: List[Dict]) -> Dict[str, Any]:
        # For HTML visual artifacts, evidence is optional
        evidence_note = ""
        if chunks:
            evidence_note = "\n\nIf relevant, incorporate these insights from Lenny's Podcast:\n"
            evidence_note += self._build_evidence_block(chunks)

        system_prompt = HTML_SYSTEM_PROMPT + evidence_note

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create the HTML artifact: {topic}"},
        ]

        logger.info(f"ArtifactSkill generating html for: '{topic}'")
        response = self.provider.chat(messages)
        content = response.get("content", "").strip()

        # Strip markdown code fences if model wraps output
        if content.startswith("```html"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        title = self._extract_html_title(content, fallback=f"HTML: {topic[:60]}")
        # Enforce restrictive Content-Security-Policy on generated HTML
        content = self.inject_csp(content, allow_scripts=False)
        logger.info(f"ArtifactSkill html done. title='{title}' chars={len(content)}")

        return {"type": "html", "title": title, "content": content}

    @staticmethod
    def inject_csp(html_content: str, allow_scripts: bool = False) -> str:
        """
        Inject a restrictive Content-Security-Policy meta tag into the HTML head.
        Enforces least privilege:
        - default-src 'none'
        - style-src 'unsafe-inline' (allows embedded styling)
        - img-src data: (blocks external tracking images; allows inline data URIs)
        - font-src data: (blocks external font CDNs)
        - connect-src 'none' (blocks fetch/XHR/WebSocket)
        - form-action 'none' (blocks form submissions)
        - base-uri 'none' (prevents base tag hijacking)
        - script-src 'none' (or 'unsafe-inline' if script explicitly allowed)
        """
        script_policy = "script-src 'unsafe-inline'" if allow_scripts else "script-src 'none'"
        csp = (
            f"default-src 'none'; "
            f"style-src 'unsafe-inline'; "
            f"img-src data:; "
            f"font-src data:; "
            f"connect-src 'none'; "
            f"form-action 'none'; "
            f"base-uri 'none'; "
            f"{script_policy};"
        )
        csp_meta = f'<meta http-equiv="Content-Security-Policy" content="{csp}">'

        if re.search(r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*>', html_content, re.IGNORECASE):
            return re.sub(
                r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*>',
                csp_meta,
                html_content,
                flags=re.IGNORECASE,
            )
        if re.search(r'<head[^>]*>', html_content, re.IGNORECASE):
            return re.sub(r'(<head[^>]*>)', rf'\1\n  {csp_meta}', html_content, count=1, flags=re.IGNORECASE)
        elif re.search(r'<html[^>]*>', html_content, re.IGNORECASE):
            return re.sub(r'(<html[^>]*>)', rf'\1\n<head>\n  {csp_meta}\n</head>', html_content, count=1, flags=re.IGNORECASE)
        else:
            return f"<!DOCTYPE html>\n<html>\n<head>\n  {csp_meta}\n</head>\n<body>\n{html_content}\n</body>\n</html>"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_evidence_block(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No evidence provided."
        text = ""
        for r in chunks[:3]:
            excerpt = r.get("text", "")[:450].strip()
            text += (
                f"Episode: {r.get('episode_title', 'Unknown')}\n"
                f"Guest: {r.get('guest', 'Unknown')}\n"
                f"Excerpt: {excerpt}...\n\n"
            )
        return text

    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract the first H1 heading from Markdown content."""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                raw = stripped[2:].strip()
                return re.sub(r"[*_]", "", raw).strip()
        return fallback

    def _extract_html_title(self, content: str, fallback: str) -> str:
        """Extract <title> tag from HTML content."""
        m = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # Try <h1>
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", content, re.IGNORECASE)
        if m:
            return re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return fallback
