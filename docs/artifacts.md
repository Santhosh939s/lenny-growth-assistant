# Artifacts: Generation & In-App Viewing

The **Lenny Growth Assistant** supports on-demand artifact generation, allowing users to request structured documents and visual user interface components directly from chat conversations.

---

## 1. What are Artifacts?

An **Artifact** is a substantial, standalone digital asset created by the assistant during a conversation. Rather than printing lengthy HTML tables or complete design documents directly inside chat bubbles, the assistant extracts them into distinct, structured assets stored in the database and rendered in a dedicated **In-App Artifact Viewer**.

---

## 2. Supported Artifact Types

### A. Markdown (`type: "markdown"`)
- **Use Case**: Deep-dive strategy playbooks, product requirement briefs, meeting summaries, and interview synthesis documents.
- **Grounding**: Automatically queries `RetrievalService` over Lenny's Podcast transcripts to ground framework points in verified operator experiences.
- **Rendering**: Converted to HTML via `marked` and purified using `DOMPurify` before insertion into the host DOM.

### B. HTML / CSS (`type: "html"`)
- **Use Case**: Visual widgets, interactive cards, pricing tiers, conversion funnels, and data tables.
- **Self-Contained**: Contains complete `<!DOCTYPE html>`, `<head>`, and `<style>` blocks with embedded CSS.
- **Rendering**: Isolated in an `<iframe>` with strict least-privilege sandboxing and Content Security Policy enforcement.

---

## 3. Data Model & PostgreSQL Persistence

Artifacts are persisted in the `artifacts` table in PostgreSQL:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique artifact identifier |
| `session_id` | UUID | Foreign Key (`chat_sessions.id`, ON DELETE CASCADE) | The session where the artifact was generated |
| `message_id` | UUID | Foreign Key (`messages.id`, ON DELETE SET NULL) | The specific assistant message that produced it |
| `type` | String(16) | NOT NULL (`markdown` or `html`) | The artifact content format |
| `title` | String(512) | NOT NULL | Human-readable title |
| `content` | Text | NOT NULL | The complete raw Markdown or HTML document |
| `created_at` | DateTime | Default UTC now | Creation timestamp |
| `updated_at` | DateTime | On update UTC now | Last modification timestamp |

---

## 4. API Endpoints

- **`GET /api/artifacts/{artifact_id}`**: Retrieves an individual artifact by its UUID. Returns 404 if not found.
- **`GET /api/artifacts/session/{session_id}`**: Lists all artifacts generated within a chat session in reverse chronological order.

---

## 5. Frontend Viewer Capabilities

The in-app **Artifact Viewer** is rendered side-by-side with the active chat:
- **Header Actions**:
  - Format Badge (`MARKDOWN` / `HTML`)
  - Security Badge (`🛡️ Sanitized DOM` or `🔒 Sandboxed`)
  - View Mode Toggle (**Preview** vs **Code** view)
  - **Copy** button to copy raw content to the clipboard
  - **Close** (✕) button to collapse the viewer back into full chat view
- **Artifact Tab Switcher**: When multiple artifacts exist in a session, users can toggle between them instantaneously.
- **In-Chat Artifact Cards**: Assistant messages include a card button ("Open in Viewer →") that immediately switches the active viewer to that artifact.

---

## 6. Security Reference
For complete details on browser security configurations, DOMPurify sanitization rules, iframe least privilege, Content Security Policy directives, and why same-origin access is intentionally disabled, see [`docs/artifact-security.md`](artifact-security.md).
