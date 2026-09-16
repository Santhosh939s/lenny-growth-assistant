# Product Requirements Document (PRD): Lenny Growth Assistant

## 1. Overview & Vision
The **Lenny Growth Assistant** is an agentic AI application that unlocks the collective wisdom of 300+ episodes of *Lenny's Podcast*. By combining dense semantic search (RAG) over podcast transcripts, local & cloud LLM orchestration, structured format generators (such as Ship 30 for 30 articles), and an in-app visual Artifact Viewer, the assistant helps operators, product managers, and founders make evidence-grounded growth decisions.

---

## 2. User & Problem Statement

### Target Users
- **Product Managers & Growth Leaders**: Seeking proven strategies for retention, activation, pricing, and team design.
- **Founders & Startup Operators**: Needing actionable playbooks from world-class operators (e.g., Brian Chesky, Shreyas Doshi, Elena Verna).
- **Writers & Content Creators**: Converting podcast insights into structured essays and framework diagrams.

### Problem Statement
Lenny’s Podcast spans 300+ in-depth interviews (over 10,000 text chunks and hundreds of hours of conversation). Key tactical insights (e.g., how Figma tested pricing, how Airbnb approached guest cancellation, or how Linear prioritizes features) are buried in hours of audio and massive text transcripts. Searching raw transcripts manually is tedious, keyword search misses semantic synonyms, and generic LLMs frequently hallucinate nonexistent quotes, episode titles, or advice.

---

## 3. Measurable Success Metrics

1. **Retrieval Grounding Accuracy (Primary Metric)**:
   - **Target**: $\ge 90\%$ of factual questions cite at least 1 verified Lenny Podcast episode with valid guest name and relevant transcript excerpt (similarity score $> 0.60$).
2. **Zero-Hallucination Source Rate**:
   - **Target**: $100\%$ of returned citations map to existing documents in the PostgreSQL knowledge base; $0\%$ fabricated episode titles or guests.
3. **Artifact Generation Success**:
   - **Target**: $100\%$ of generated HTML and Markdown artifacts conform to browser security isolation (0 script injections into parent DOM, 100% CSP compliance).
4. **Local Execution Feasibility**:
   - **Target**: Operable on commodity hardware (8 GB RAM, CPU-only laptop) without crashing or exhausting host memory.

---

## 4. Key Assumptions

- **Users**: Users prefer concise, attributed answers with transparent source citations over unsupported conversational text.
- **Transcripts**: The local transcript repository (`lennys-podcast-transcripts`) is structured with YAML frontmatter containing metadata (`guest`, `title`, `youtube_url`, `publish_date`).
- **Models**: The default local model is Ollama with `qwen3:1.7b` for text generation and `nomic-embed-text` for embeddings. A cloud model (Anthropic Claude 3.5 Sonnet / Haiku) is configurable for higher throughput.
- **Hardware**: The system must run on CPU-only machines with limited memory footprint ($\le 8$ GB RAM).

---

## 5. Scope

### In-Scope (Functional Milestones 1–6)
- **Session & Chat Persistence**: PostgreSQL persistence for user sessions, messages, and metadata.
- **Knowledge Base & Ingestion**: YAML frontmatter parsing, chunking (with overlap), SHA-256 idempotency hashing, vector embeddings, and cosine similarity search.
- **Agentic Conversational Layer**: Provider abstraction (Ollama & Anthropic), dynamic tool calling (`search_lenny_knowledge`, `write_ship30_article`), and deterministic fallback.
- **Ship 30 for 30 Skill**: Structured essay generator (H1 title, hooks, clear sections, bullet points, exact word count calculation, source attribution).
- **Artifact Generation & Viewer**: Dedicated split-screen Artifact Viewer for Markdown (DOMPurify sanitized) and HTML/CSS (least-privilege iframe sandbox with strict Content Security Policy).
- **System Health & Diagnostics**: Structured `/health` endpoint reporting database, provider, and Ollama connectivity.

### Out-of-Scope (Intentionally Excluded)
- Full audio/video processing and direct YouTube downloading.
- Multi-tenant enterprise team management and billing systems.
- Live web crawling or external search engines.
- Write-access to transcript source files (knowledge base is read-only).

---

## 6. Risks & Tradeoffs

| Risk / Tradeoff | Impact | Mitigation Strategy |
|-----------------|--------|---------------------|
| **Local CPU Model Latency** | Qwen 1.7B on CPU takes 30–60s per response for long-form generation. | Deterministic routing for artifacts and tools bypasses unnecessary multi-turn LLM loops. Cloud provider (Anthropic) is one env-var toggle away for instant latency. |
| **Python NumPy Cosine Similarity vs. pgvector** | Scanning 10,000 embeddings in memory takes ~2–3 seconds instead of milliseconds in native pgvector. | Eliminates complex Windows C++ compiler dependencies for pgvector. Chunks are filtered to embedded records and processed using vectorized NumPy matrix operations. |
| **Transcript Source Rights & Licensing** | Transcript text is copyrighted by Lenny Rachitsky / Lenny's Podcast. | Transcripts are never copied into the application repository. The repository path is configured via `TRANSCRIPT_SOURCE_DIR`. Application acts strictly as a local search interface over the user's clone. |
| **Generated HTML Security** | LLMs could generate malicious script tags or clickjacking attempts. | Dual defense: (1) Static HTML uses `sandbox=""` (no scripts allowed). (2) Restrictive Content Security Policy (`connect-src 'none'; default-src 'none'; img-src data:;`) blocks all network exfiltration. |
| **Knowledge Freshness** | As new podcast episodes are released, the local database becomes dated. | Incremental ingestion pipeline uses SHA-256 content hashing to scan and ingest only newly added or modified episodes idempotently. |
