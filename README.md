# The Lenny Growth Assistant

An agentic AI research assistant and visual artifact generator trained on **300+ episodes of Lenny’s Podcast**. Built with a high-performance **FastAPI** backend, dense semantic search over transcript embeddings, **PostgreSQL** persistence, an isolated **Claude-style in-app Artifact Viewer**, and a lightweight **React 19** frontend.

---

## 1. Problem Statement & Overview

Lenny’s Podcast features hundreds of hours of tactical advice from world-class startup operators, founders, and product leaders (including Brian Chesky, Shreyas Doshi, Elena Verna, and Gustaf Alströmer). However:
- Valuable frameworks are buried across 10,000+ chunks of conversational transcripts.
- Keyword searches fail to recognize operational synonyms (e.g. "cohort retention" vs "churn stabilization").
- Generic foundation models hallucinate quotes, episode titles, or non-existent guests.

The **Lenny Growth Assistant** solves this by:
1. Grounding every factual answer in verified podcast transcript excerpts with citations.
2. Generating atomic, structured essays via a dedicated **Ship 30 for 30 Skill**.
3. Generating rich, interactive **Markdown & HTML/CSS Artifacts** rendered in a sandboxed in-app viewer.

---

## 2. Key Product & Architectural Decisions

- **Zero-Dependency Vector Retrieval**: Embeddings (`nomic-embed-text`, 768-dim) are stored in standard PostgreSQL JSONB arrays and evaluated using vectorized **NumPy** cosine similarity in memory. This eliminates complex C++ compiler requirements for `pgvector` on Windows while delivering sub-3-second scans across 10,000+ chunks.
- **Deterministic Routing**: Small local models (Qwen 1.7B) frequently fail complex ReAct tool loops. The orchestrator uses deterministic routing for high-intent tasks (Ship 30 articles and HTML/Markdown artifacts) and dynamic tool calling with semantic fallback for general questions.
- **Least-Privilege Iframe Sandboxing & CSP**: Generated HTML artifacts are treated as **untrusted content**. They run inside an `<iframe>` with `sandbox=""` (or `sandbox="allow-scripts"` when scripts are needed). `allow-same-origin` is **never** granted. A strict Content Security Policy (`connect-src 'none'; img-src data:; default-src 'none';`) blocks outbound network exfiltration.
- **DOMPurify Markdown Sanitization**: Generated Markdown is purified with `DOMPurify` before DOM insertion to purge any embedded scripts, event handlers, or malicious frames.
- **Provider Agnostic**: Switch between local Ollama (`qwen3:1.7b`) and cloud Anthropic (`claude-3-5-sonnet-20241022`) with a single environment variable.

---

## 3. Architecture Overview

```
React 19 Frontend  <─── REST API ───>  FastAPI Backend  <─── SQLAlchemy ───>  PostgreSQL
       │                                     │                                      │
   Chat & Viewer                      AgentService                           Sessions, Msgs,
(DOMPurify + CSP)                     ├─ RetrievalService (NumPy)            Chunks & Artifacts
                                      ├─ Ship30Skill / ArtifactSkill
                                      └─ LLMProvider (Ollama / Anthropic)
```

---

## 4. Prerequisites

- **Python 3.8+** (Python 3.8 – 3.12 supported)
- **Node.js 18+** (Node 20+ / 22+ recommended)
- **PostgreSQL 14+** (Local service running on port 5432 or containerized)
- **Ollama** (for local CPU/GPU model execution)
- **Git**

---

## 5. Local Setup Step-by-Step

### A. Clone the Repository
```bash
git clone https://github.com/your-username/lenny-growth-assistant.git
cd lenny-growth-assistant
```

### B. Configure Environment Variables
Copy `.env.example` to `backend/.env`:
```bash
cp .env.example backend/.env
```
Edit `backend/.env` to configure your local environment:
```env
# PostgreSQL connection string
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lenny_assistant

# Path to the local clone of Lenny's Podcast Transcripts
TRANSCRIPT_SOURCE_DIR=C:\Users\username\Desktop\lennys-podcast-transcripts

# Model provider: "ollama" (local) or "anthropic" (cloud)
MODEL_PROVIDER=ollama

# Local Ollama settings
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=qwen3:1.7b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Optional Cloud Anthropic settings
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### C. PostgreSQL Setup & Migrations
1. Create the database in PostgreSQL:
```sql
CREATE DATABASE lenny_assistant;
```
2. Apply all Alembic database migrations:
```bash
cd backend
alembic upgrade head
```

### D. Ollama Setup
1. Download and start [Ollama](https://ollama.ai).
2. Pull the required models:
```bash
ollama pull qwen3:1.7b
ollama pull nomic-embed-text
```

### E. Transcript Repository Setup & Ingestion
Clone the transcripts repository outside this project:
```bash
git clone https://github.com/your-username/lennys-podcast-transcripts.git ../lennys-podcast-transcripts
```
Run the idempotent ingestion CLI:
```bash
cd backend
python -m app.cli ingest
```
This scans all `transcript.md` files, parses YAML metadata, chunks content, computes embeddings, and stores them in PostgreSQL. Subsequent runs compute SHA-256 hashes to skip unchanged files.

---

## 6. Running the Application

### Start the Backend
```bash
cd backend
python -m uvicorn app.main:app --port 8000 --reload
```
API available at `http://127.0.0.1:8000`. Health status at `http://127.0.0.1:8000/health`.

### Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 7. Running the Test Suite

### Backend Pytest Suite (34 Tests)
```bash
cd backend
python -m pytest tests/ -v
```

### Frontend Security & Unit Tests (5 Tests)
```bash
cd frontend
npm test
```

### Production Frontend Build
```bash
cd frontend
npm run build
```

---

## 8. Model Provider Switching

To switch from local Ollama to cloud Anthropic:
1. In `backend/.env`, set:
   ```env
   MODEL_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
   ```
2. Restart the backend server.
3. Verify `/health` reports `"provider": "anthropic"`. No code changes required.

---

## 9. Artifact Viewer & Security Architecture

The Lenny Growth Assistant treats all LLM-generated artifacts as **untrusted content**:

| Capability | Markdown Artifacts | HTML Artifacts |
|------------|-------------------|----------------|
| **Execution Context** | Host Application DOM | Sandboxed `<iframe>` |
| **Sanitizer** | `DOMPurify` (Strict profile) | Browser Sandbox + CSP |
| **Scripts Allowed** | **None** (`<script>` stripped) | Only if requested (`sandbox="allow-scripts"`); default is `sandbox=""` |
| **Same-Origin Access** | Inherited (safe, scripts stripped) | **Disabled** (`null` opaque origin; cannot access `parent.document`, cookies, or localStorage) |
| **Network Requests** | **None** | **Blocked** (`connect-src 'none'`; `fetch`/`XHR`/`WS` rejected) |
| **External Images** | Sanitized `http:`/`https:` | **Blocked** (`img-src data:`; tracking pixels disabled) |

For comprehensive security specifications, see [`docs/artifact-security.md`](docs/artifact-security.md).

---

## 10. Demo & User Instructions

1. **Ask a Grounded Question**:
   - Type: *"What did Lenny's guests say about choosing a North Star metric?"*
   - Observe the cited episode titles, guest names, and similarity scores.
2. **Generate a Ship 30 for 30 Article**:
   - Type: *"Write a Ship 30 for 30 article about how product teams should prioritize features."*
   - Observe the 1200+ word atomic essay with headers, bullet points, and exact calculated word count.
3. **Generate an Artifact**:
   - Type: *"Create an HTML pricing card for a SaaS product."*
   - Observe the Artifact Card in chat and the split-screen **Artifact Viewer** opening automatically.
   - Toggle between **Preview** and **Code** mode; test the **Copy** button.

---

## 11. Known Limitations

- **Local CPU Model Latency**: On commodity 8 GB RAM laptops without dedicated GPUs, Qwen 1.7B generation requires 30–60 seconds per response. For real-time sub-second responses, use `MODEL_PROVIDER=anthropic`.
- **In-Memory Cosine Similarity**: NumPy in-memory scanning is optimal up to $\approx 50,000$ chunks. For larger corpuses ($> 500,000$ chunks), migrating to PostgreSQL `pgvector` with HNSW indexing is recommended.

---

## 12. Source Content Rights & Disclaimer

This application uses the [Lenny's Podcast Transcripts](https://github.com/karpathy/free-lenny-transcripts) repository as a configurable local knowledge source. 
- All podcast audio, interview transcripts, and guest opinions remain the intellectual property of **Lenny Rachitsky** and *Lenny's Podcast*.
- This repository does **not** host, republish, or claim ownership of the raw transcripts.
- Users must clone the transcript repository independently and adhere to all applicable licensing and fair-use rights.
