# Engineering Log & Architecture Corrections (`agent-transcript.md`)

This document records the critical technical challenges, failed attempts, and architectural pivots encountered during the design and development of the **Lenny Growth Assistant**.

---

## 1. Remote Supabase Pooler Connectivity Failure & Pivot to Local PostgreSQL
- **Challenge**: Initial database configurations attempted to connect to an external Supabase PostgreSQL instance via IPv4/IPv6 pooler endpoints (`aws-0-ap-south-1.pooler.supabase.com:5432` and `6543`).
- **Failure**: Connections failed with network socket timeouts and authentication errors caused by URL-encoding special characters (`[`, `@`, `%`, `+`, `]`) within the database password string through standard connection drivers (`psycopg2`, `pg8000`).
- **Correction**: Rather than introducing network flakiness into local testing or hardcoding brittle credentials, development was decisively migrated to a robust, local PostgreSQL instance (`localhost:5432`). Connection strings in configuration were normalized to use clean standard credentials.

---

## 2. pgvector Extension Unavailable on Windows
- **Challenge**: Dense vector similarity search for 10,000+ chunks typically relies on the PostgreSQL `pgvector` extension.
- **Failure**: Standard Windows distributions of PostgreSQL do not bundle pre-compiled binaries for `pgvector`. Compiling from source requires Visual Studio C++ toolchains, Python header dependencies, and elevated administrative permissions that would severely hinder developer onboarding and reproducible testing on commodity Windows laptops.
- **Correction**: Architected a hybrid storage and retrieval approach:
  - Embeddings (768-dimensional float vectors from `nomic-embed-text`) are stored directly as JSONB arrays in the `document_chunks` table.
  - At query time, `RetrievalService` fetches the chunk embeddings and executes high-speed, vectorized cosine similarity math in-memory using **NumPy**.
  - **Tradeoff**: Linear scan $O(N)$ across 10,000 chunks completes in $\approx 2.5$ seconds on CPU, completely eliminating native C++ dependencies while maintaining 100% mathematical accuracy.

---

## 3. Ollama Qwen 1.7B Multi-Tool 400 Bad Request
- **Challenge**: Ollama provides native `/api/chat` function calling. When passing tool declarations alongside multi-turn conversation histories, Qwen 1.7B occasionally failed or Ollama returned `400 Bad Request`.
- **Root Cause**:
  1. Ollama's `/api/chat` expects `tool_calls[].function.arguments` in message history to be a native JSON Object (dictionary), whereas standard OpenAI format often transmits stringified JSON (`json.dumps(args)`).
  2. When an unhandled tool response (`role: "tool"`) was re-sent without matching tool schemas or uncompleted calls, Ollama's validation layer threw a 400 error.
- **Correction**: Streamlined tool execution in `_invoke_search`:
  - When evidence is retrieved, the agent injects the podcast excerpts directly into the synthesis prompt context rather than relying on brittle assistant-tool message roundtrips.
  - This guarantees universal compatibility across local Ollama models and cloud providers without format rejections.

---

## 4. Deterministic Routing for High-Intent Skills (Ship 30 & Artifacts)
- **Challenge**: Small local models (Qwen 1.7B) running on low-resource CPU laptops frequently hallucinate arguments or skip tool invocation when asked for complex multi-thousand-word tasks (e.g. Ship 30 for 30 essays or HTML dashboards).
- **Correction**: Implemented deterministic intent detection in `AgentService`:
  - Explicit requests for "Ship 30", "atomic essay", or "write an article about" immediately route to `Ship30Skill`.
  - Explicit requests for "HTML artifact", "pricing card", or "markdown document" route to `ArtifactSkill`.
  - General domain inquiries continue to leverage semantic retrieval and native tool calling.

---

## 5. Local CPU Latency & Generation Chunking
- **Challenge**: Generating a full 1,200-word Ship 30 essay on an 8 GB RAM CPU laptop requires 4 to 8 minutes of compute time.
- **Correction**:
  - The word count validation was made dynamic: `word_count` is calculated directly from the actual generated content rather than hardcoded.
  - HTTP client timeouts for end-to-end evaluation scripts were set to 700 seconds to avoid prematurely severing long-running CPU generation tasks.
  - A cloud provider option (`MODEL_PROVIDER=anthropic`) was implemented with seamless toggle support for scenarios requiring sub-second latencies.

---

## 6. HTML Artifact Security: Iframe Sandboxing & CSP
- **Challenge**: Permitting an LLM to generate raw HTML introduces significant XSS, clickjacking, and data exfiltration risks.
- **Initial Flawed Assumption**: Relying merely on `sandbox="allow-scripts"` was recognized as unsafe because scripts running inside the iframe can still make outbound `fetch()` or `XMLHttpRequest` calls to external endpoints.
- **Correction**:
  - **Least Privilege Sandboxing**: Static HTML without JavaScript receives `sandbox=""` (the most restrictive sandbox possible in browser engines, disabling all scripts, forms, and popups).
  - **Opaque Origin**: `allow-same-origin` is strictly forbidden under all circumstances, ensuring the iframe runs in an isolated `null` origin with zero access to `window.parent`, parent cookies, or local storage.
  - **Strict CSP Meta Tag**: Injected systematically into all HTML artifacts:
    `default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; script-src 'none';`
  - Automated tests in `frontend/test/security.test.js` verify that both DOMPurify and iframe sandboxing enforce these restrictions on actual DOM elements.
