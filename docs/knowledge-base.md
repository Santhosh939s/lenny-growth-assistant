# Knowledge Base and RAG Retrieval Layer

This document outlines the architecture for the knowledge base in the Lenny Growth Assistant.

## Transcript Source
The assistant reads raw podcast transcripts from a configurable local path (`LENNY_TRANSCRIPTS_PATH`). These transcripts are markdown files with YAML frontmatter containing rich metadata such as guest name, episode title, and YouTube URL.

## Ingestion Flow
The ingestion pipeline is a standalone Python service (`app/services/ingestion_service.py`) triggered via CLI.
1. It recursively discovers all `transcript.md` files in the source directory.
2. It parses the YAML frontmatter and extracts the core text.
3. It chunks the text into overlapping segments (default ~500 words with 50-word overlap) to preserve context.
4. It calls the local Ollama API to generate a vector embedding (using `nomic-embed-text`) for each chunk.
5. It computes a SHA-256 hash of the transcript content. This makes the ingestion idempotent: unchanged files are skipped instantly, while modified files have their old chunks replaced.

## Indexing & Storage Approach
> [!NOTE]
> **Why No pgvector?**
> The local development environment uses a standard Windows PostgreSQL installation which does not bundle `pgvector`. To adhere to constraints and avoid forcing users to compile native C extensions on Windows, we utilize a PostgreSQL-compatible fallback.

Embeddings are safely stored as pure JSON/JSONB arrays within the `document_chunks` table in PostgreSQL. The metadata is also stored flat in each chunk's JSONB column to prevent expensive table joins during retrieval.

## Retrieval Approach
Since we store embeddings in JSON arrays, the retrieval happens in-memory on the Python backend:
1. The user's query is embedded using Ollama (`nomic-embed-text`).
2. The `RetrievalService` fetches all chunk embeddings from PostgreSQL.
3. We utilize `numpy` to perform high-speed cosine similarity across all vectors.
4. The chunks with the highest similarity scores are returned.

## Source Tracing
Every retrieved chunk is bundled with its exact source metadata, ensuring the future AI agent can accurately cite the guest, episode, and even provide a link back to the YouTube video!

## Refreshing the Knowledge Base
To re-ingest new or changed transcripts, simply run:
```bash
python -m app.cli ingest
```
This is fully idempotent. Existing data will not be duplicated.

## Current Limitations
- In-memory retrieval scales well to tens of thousands of chunks (which easily covers hundreds of transcripts), but for a massive database (millions of chunks), `pgvector` will eventually need to be introduced to push the cosine similarity math back down into the database engine.
