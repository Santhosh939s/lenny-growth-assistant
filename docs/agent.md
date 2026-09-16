# Agent Architecture & Routing

The **Lenny Growth Assistant** orchestrates multi-turn conversations, domain-specific retrieval-augmented generation (RAG), and structured skills via a centralized orchestrator (`AgentService`).

---

## 1. Provider Abstraction (`LLMProvider`)

To ensure portability between local commodity hardware and high-throughput cloud models without code changes, the application uses an abstract provider interface:

```python
class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Returns {'content': str, 'tool_calls': List[Dict]}"""
        pass
```

### Supported Providers:
- **`OllamaProvider`** (`app/services/llm/ollama_provider.py`): Connects to local Ollama (`qwen3:1.7b` chat and `nomic-embed-text` embeddings).
- **`AnthropicProvider`** (`app/services/llm/anthropic_provider.py`): Connects to Anthropic Claude models (e.g., `claude-3-5-sonnet-20241022`, `claude-3-haiku`). Translates between OpenAI-standard schemas and Anthropic's native `tool_use` / `tool_result` protocol.

### Switching Providers:
Configured purely via the `MODEL_PROVIDER` environment variable:
```bash
# Local execution (default)
MODEL_PROVIDER=ollama

# Cloud execution
MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

---

## 2. Routing Hierarchy

To achieve high reliability on small local models (such as Qwen 1.7B) that may struggle with complex ReAct loops, `AgentService.process_message()` implements a prioritized routing hierarchy:

```
User Message
    │
    ├─► [1] Is HTML Artifact Request?  ──► ArtifactSkill(type='html')  ──► Output (no RAG by default)
    │
    ├─► [2] Is Markdown Doc Request?   ──► ArtifactSkill(type='markdown') ──► RAG Search ──► Markdown Document
    │
    ├─► [3] Is Ship 30 Request?        ──► Ship30Skill ──► RAG Search ──► 1200w Atomic Essay
    │
    ├─► [4] Native LLM Tool Calling    ──► search_lenny_knowledge / write_ship30_article
    │
    └─► [5] Fallback Retrieval Scan     ──► If similarity > 0.60 ──► RAG Search ──► Synthesis
                                             Else ──► Conversational direct answer
```

1. **Deterministic Artifact Routing**: Matches explicit keywords (e.g., "create an html pricing card", "generate a markdown document") directly to `ArtifactSkill`.
2. **Deterministic Ship 30 Routing**: Matches "ship 30", "atomic essay", or "write an article about" directly to `Ship30Skill`.
3. **Native Tool Calling**: For general prompts, the LLM is provided with tool declarations (`search_lenny_knowledge` and `write_ship30_article`).
4. **Deterministic Fallback**: If the model answers conversationally without invoking a tool, but the query has semantic similarity $> 0.60$ against transcript chunks, the agent automatically executes retrieval and injects evidence for synthesis.

---

## 3. Conversational History & Session Context
- Up to 10 previous messages from the active session are formatted into standard role-based history (`user` / `assistant`).
- System prompts enforce strict persona rules: grounding claims in Lenny's podcast, maintaining an encouraging and analytical tone, and avoiding generic fluff.

---

## 4. Grounding & Insufficient Evidence Policy
- When factual evidence is retrieved, the synthesized answer must cite the specific episode title and guest.
- **Insufficient Evidence Policy**: If retrieved chunks have low similarity ($< 0.60$) or do not contain direct answers, the assistant explicitly clarifies that the topic was not discussed in available Lenny episodes and provides general industry guidance without fabricating citations.
