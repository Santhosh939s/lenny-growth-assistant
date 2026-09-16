# System Architecture: Lenny Growth Assistant

## 1. System Overview & Component Diagram

```
+-------------------------------------------------------------------------------+
|                               Frontend (React 19)                            |
|  +------------------------+  +---------------------------------------------+  |
|  |   Sidebar / Sessions   |  |   Chat Area (Bubbles + Source Citations)   |  |
|  +------------------------+  +---------------------------------------------+  |
|                              |      In-App Artifact Viewer (Split-Pane)    |  |
|                              |   - Markdown: DOMPurify Strict Sanitization |  |
|                              |   - HTML/CSS: Sandboxed <iframe> + CSP      |  |
|                              +---------------------------------------------+  |
+--------------------------------------▲----------------------------------------+
                                       │ HTTP / REST API (JSON)
+--------------------------------------▼----------------------------------------+
|                               FastAPI Backend                                 |
|                                                                               |
|  +--------------------+   +------------------------------------------------+  |
|  | API Endpoints      |   | ChatService                                    |  |
|  | - /api/sessions    |   | - Session management                           |  |
|  | - /api/knowledge   |   | - Message history persistence                  |  |
|  | - /api/artifacts   |   | - Artifact linking                             |  |
|  | - /health          |   +-----------------------┬------------------------+  |
|  +--------------------+                           │                           |
|                                                   ▼                           |
|                         +--------------------------------------------------+  |
|                         | AgentService (Orchestrator)                      |  |
|                         | - Deterministic routing (Ship30, Artifacts)      |  |
|                         | - Dynamic tool calling fallback                  |  |
|                         +-----------┬──────────────┬───────────────────────+  |
|                                     │              │                          |
|             ┌───────────────────────┼──────────────┼─────────────────┐        |
|             ▼                       ▼              ▼                 ▼        |
|  +--------------------+   +-----------------+  +------------+  +-----------+  |
|  | RetrievalService   |   | LLM Provider    |  | Ship30Skill|  |Artifact-  |  |
|  | - Ollama embedding |   | - OllamaProvider|  | - 1200w    |  |  Skill    |  |
|  | - In-memory cosine |   | - Anthropic     |  |   Atomic   |  | - Markdown|  |
|  |   similarity (np)  |   |   Provider      |  |   Format   |  | - HTML+CSP|  |
|  +--------------------+   +-----------------+  +------------+  +-----------+  |
+--------------------------------------┬----------------------------------------+
                                       │ SQLAlchemy 2.0 / Alembic
+--------------------------------------▼----------------------------------------+
|                           PostgreSQL Database                                 |
|  +--------------------+   +--------------------+   +-----------------------+  |
|  | users              |   | chat_sessions      |   | messages              |  |
|  +--------------------+   +--------------------+   +-----------------------+  |
|  | documents          |   | document_chunks    |   | artifacts             |  |
|  +--------------------+   +--------------------+   +-----------------------+  |
+-------------------------------------------------------------------------------+
```

---

## 2. Component Deep Dive & Architectural Tradeoffs

### 1. Frontend: React 19 + Vanilla CSS (No Heavy UI Frameworks)
- **Design Decision**: Built using React 19 and raw CSS instead of heavy component frameworks (Tailwind, Material-UI, or AntD).
- **Tradeoff**:
  - *Advantage*: Extremely lightweight client bundle (Vite bundle size $< 100$ kB gzipped), zero CSS bloat, instantaneous compilation (sub-second build), and maximum control over custom glassmorphism and animations.
  - *Cost*: Requires writing and maintaining explicit CSS utility classes and media queries manually.

### 2. Backend: FastAPI + Asynchronous Architecture
- **Design Decision**: FastAPI was selected for high-throughput asynchronous request handling, automatic OpenAPI schema generation, and dependency injection (`Depends(get_db)`).
- **Tradeoff**:
  - *Advantage*: Native support for Python typing, Pydantic request/response validation, and clean lifecycle management (`lifespan`).
  - *Cost*: Asynchronous route handlers require strict attention to synchronous database sessions (`SessionLocal`) to prevent thread pool deadlocks.

### 3. Database & Migrations: PostgreSQL with SQLAlchemy and Alembic
- **Design Decision**: PostgreSQL is the single source of truth for sessions, message histories, transcript metadata, vector chunks, and artifacts.
- **Tradeoff**:
  - *Advantage*: Full ACID compliance, cascade deletions (`ondelete="CASCADE"`), and reproducible database versioning via Alembic migrations.
  - *Cost*: Requires a running PostgreSQL instance (local or containerized) rather than a self-contained zero-config SQLite file.

### 4. Vector Search: NumPy In-Memory Cosine Similarity vs. pgvector
- **Design Decision**: The embeddings (`nomic-embed-text`, 768 dimensions) are stored as JSONB / Float arrays in PostgreSQL. At query time, embeddings are evaluated using vectorized NumPy cosine similarity in memory.
- **Tradeoff**:
  - *Advantage*: Eliminates the complex native C++ build toolchain and OS-level shared library dependencies required to compile the `pgvector` extension on Windows. Runs identically on any machine with standard PostgreSQL.
  - *Cost*: Linear scan complexity $O(N)$ over 10,000 chunks takes ~2–3 seconds on CPU. For datasets $> 100,000$ chunks, migrating to indexed `pgvector` (HNSW / IVFFlat) would be necessary.

### 5. Orchestration: Deterministic Router + ReAct Fallback
- **Design Decision**: `AgentService` employs deterministic keyword filters for high-intent requests (Ship 30 essays and Artifacts), paired with dynamic LLM tool calling and fallback retrieval.
- **Tradeoff**:
  - *Advantage*: Small local models (Qwen 1.7B) frequently fail or produce invalid JSON when tasked with multi-step ReAct loops. Deterministic routing guarantees that article requests and HTML requests invoke their respective skills 100% of the time without unnecessary model latency.
  - *Cost*: Keyword triggers require careful prompt phrasing guidelines.

### 6. Security Isolation: DOMPurify and Sandboxed Iframe with CSP
- **Design Decision**: Markdown is rendered in the host DOM via `DOMPurify`. HTML artifacts are rendered inside an isolated `<iframe>` configured with `sandbox=""` or `sandbox="allow-scripts"` and a restrictive Content Security Policy (`connect-src 'none'`).
- **Tradeoff**:
  - *Advantage*: Total defense in depth against XSS, token theft, cookie hijacking, and covert outbound network exfiltration.
  - *Cost*: The iframe cannot share theme CSS variables with the parent window; styling must be completely self-contained in the artifact.
