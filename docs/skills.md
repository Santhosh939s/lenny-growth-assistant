# Skills: Ship 30 for 30

## Why Ship 30 is a Dedicated Skill

"Ship 30 for 30" is a structured, opinionated writing format. Embedding its logic directly inside `AgentService` or as a raw prompt string would:

1. Violate the single-responsibility principle — the agent orchestrates, skills specialize.
2. Make the capability impossible to test independently without spinning up the full agent.
3. Tie the format rules to the chat routing logic, making both harder to evolve.

By isolating it in `app/services/skills/ship30.py`, the skill can be:
- Invoked independently from tests with a mock LLM provider.
- Versioned and updated without touching the agent router.
- Extended (e.g., adding other essay formats) following the same pattern.

---

## Invocation Conditions

The `AgentService` exposes a `write_ship30_article` tool to the LLM. The LLM is instructed to call this tool **only** when the user explicitly requests:

- A Ship 30 for 30 article or essay
- An article, post, or written piece about a topic
- Content to be written in a structured format

**Normal conversational questions** (e.g., "What did Lenny say about onboarding?") must **not** invoke this tool — they route through `search_lenny_knowledge` instead.

---

## Input / Output Contract

### Input

```python
Ship30Skill.generate_article(
    topic: str,          # The article topic string
    chunks: List[Dict],  # Retrieved evidence from RetrievalService
)
```

Each chunk must contain:

| Key              | Type  | Description                         |
|------------------|-------|-------------------------------------|
| `episode_title`  | str   | Title of the Lenny podcast episode  |
| `guest`          | str   | Guest's name                        |
| `text`           | str   | Retrieved transcript excerpt        |
| `similarity`     | float | Cosine similarity score             |
| `youtube_url`    | str   | YouTube URL (optional, may be None) |

### Output

```json
{
  "type":       "ship30",
  "title":      "The Article Title",
  "content":    "# The Article Title\n\nFull Markdown...",
  "word_count": 1243,
  "sources": [
    {
      "title":       "How to build a great product",
      "guest":       "Shreyas Doshi",
      "similarity":  0.92,
      "youtube_url": "https://www.youtube.com/watch?v=..."
    }
  ]
}
```

> [!IMPORTANT]
> `word_count` is **always calculated from the actual generated content** — it is never hardcoded or forced to 1250. 1,250 words is the target, but the actual count depends on the LLM output.

---

## Grounding Approach

1. **RetrievalService is always called first.** `AgentService` retrieves the top-5 relevant chunks before passing them to `Ship30Skill`.
2. **Evidence is passed explicitly.** The skill's system prompt includes the full evidence block — the LLM cannot fabricate information it wasn't given.
3. **Fabrication is prohibited in the prompt.** The skill's prompt explicitly instructs the model not to:
   - Invent direct quotations
   - Invent statistics or data
   - Invent episode titles, guests, or URLs
4. **Source integrity is enforced in code.** The `sources` list is built from the input `chunks` only — never from parsed LLM output. A test verifies this.

---

## Formatting Requirements

The generated article must follow Ship 30 for 30 style:

- **H1 title** on the first line (`# Title`)
- **Strong hook** in the opening paragraph
- **Skimmable H2 headings** for each section
- **Short paragraphs** (1–3 sentences)
- **Bullets** where appropriate
- **Bold emphasis** on key points
- **Actionable takeaway** section near the end
- **No Sources section in the article body** — sources are tracked structurally and appended by the system

---

## Source Attribution

Sources are appended to the assistant message `meta` field:

```json
{
  "type": "ship30",
  "title": "...",
  "word_count": 1243,
  "sources": [ ... ]
}
```

The `sources` list contains only episodes from the retrieved chunks. Sources are deduplicated by `episode_title`. YouTube URLs are included when available in the knowledge base — no URLs are fabricated.

---

## Limitations of the Local Model (`qwen3:1.7b`)

| Limitation               | Impact                                                    |
|--------------------------|-----------------------------------------------------------|
| Small context window     | Very long evidence blocks may be silently truncated       |
| Slow on CPU              | Article generation takes 2–5 minutes on an 8 GB laptop   |
| Unreliable tool calling  | Native tool dispatch can fail; AgentService has a fallback |
| Output length            | May produce shorter articles (~600–900 words) instead of 1,250 |
| Format adherence         | May occasionally omit H1 or headings; system prompt mitigates this |

For production use, switch to `MODEL_PROVIDER=anthropic` in `.env` for significantly better reliability and output quality.
