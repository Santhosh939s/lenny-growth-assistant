# Artifact Security & Isolation Architecture

This document describes the security architecture for generating and rendering user-facing artifacts (Markdown and HTML/CSS) in the Lenny Growth Assistant.

---

## 1. Threat Model: Why Generated Artifacts Are Treated as Untrusted Content

LLM outputs are non-deterministic, probabilistic text generated based on prompts and third-party context (including retrieved podcast transcripts or external inputs). If an attacker manipulates retrieval content (prompt injection) or if an LLM hallucinates unintended code, untrusted markup or scripts can be generated.

Treating generated artifacts as **untrusted content** means:
- **No direct DOM injection**: Raw strings from the model are never inserted into the application DOM without sanitization.
- **Strict isolation for HTML**: Any rendered HTML must be confined to a sandboxed execution context where it cannot steal parent session tokens, access cookies, manipulate parent DOM, or execute unauthorized cross-origin requests.
- **Defense in Depth**: Even if one layer (e.g., prompt instructions or regex filters) fails, browser-enforced security boundaries (DOMPurify, iframe sandboxing, and Content Security Policy) prevent exploitation.

---

## 2. Markdown Rendering Policy

Markdown documents are rendered directly into the host application UI, which provides rich typography and readable formatting.

### What Markdown Permits
- Standard semantic markup: Headings (`#`, `##`, `###`), paragraphs, blockquotes, unordered/ordered lists, horizontal rules.
- Typography styling: bold (`**`), italic (`*`), strikethrough (`~~`), inline code (`` `code` ``), fenced code blocks (```` ``` ````).
- Standard data tables (`| header |`, `|---|`).
- Safe hyperlinks with explicit `http:` or `https:` protocols.

### What Markdown Blocks / Strips
- **DOMPurify Sanitization**: The raw HTML produced by the Markdown parser (`marked`) is filtered through `DOMPurify` before DOM insertion.
- **Blocked HTML Elements**: `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `<input>`, `<button>`, `<base>`, `<meta>`, `<link>`.
- **Blocked Attributes**: All inline JavaScript event handlers (`onerror`, `onload`, `onclick`, `onmouseover`, `onfocus`, etc.) and dangerous attributes (`style` tags/attributes that could exploit CSS expressions).
- **Dangerous Schemes**: Any link with `javascript:`, `vbscript:`, or `data:text/html` is stripped.
- **Result**: Unsanitized generated content is never injected into the application DOM.

---

## 3. HTML Rendering Policy & Least-Privilege Sandboxing

HTML artifacts (e.g., visual dashboards, tables, cards, pricing matrices) are rendered inside an isolated `<iframe>`.

### Least-Privilege Iframe Sandboxing
The `sandbox` attribute restricts the capabilities of the document embedded in the `<iframe>`.

1. **Static HTML (No JavaScript required)**:
   - Evaluated using `getIframeSandbox(content)`.
   - Uses the **most restrictive sandbox possible**: `sandbox=""` (empty attribute).
   - In standard browser behavior, an empty sandbox attribute applies ALL sandbox restrictions:
     - Scripts are completely disabled (cannot execute).
     - Forms are disabled (cannot submit).
     - Popups and new windows are disabled.
     - Top-level navigation is disabled.
     - Origin is treated as an opaque `null` origin.

2. **Interactive HTML (When JavaScript is genuinely required)**:
   - Uses strictly: `sandbox="allow-scripts"`.
   - Only enables script execution inside the isolated iframe context.
   - **NEVER** includes `allow-same-origin`.
   - **NEVER** includes `allow-top-navigation`.
   - **NEVER** includes `allow-popups`.
   - **NEVER** includes `allow-forms`.
   - **NEVER** includes `allow-modals`.

---

## 4. Why Same-Origin Access Is Intentionally Disabled

If an iframe is configured with `allow-same-origin` alongside `allow-scripts`, the script inside the iframe runs in the **same origin** as the parent application (`http://127.0.0.1:8000` or the frontend host).

This would allow malicious or compromised scripts to:
- Access `window.parent.document` and read or rewrite the chat interface.
- Read sensitive data stored in `localStorage`, `sessionStorage`, or cookies.
- Impersonate the user and make authenticated API calls on the user's behalf.
- Evade iframe isolation entirely.

By **intentionally omitting `allow-same-origin`**, browsers assign the iframe a unique, opaque origin (`null`). Cross-origin security boundaries prevent any script within the iframe from accessing `window.parent` or any storage/cookies belonging to the host application.

---

## 5. Content Security Policy (CSP): Network & Resource Restrictions

Relying solely on `sandbox="allow-scripts"` is insufficient because scripts running inside an iframe can still attempt outbound network requests (e.g., via `fetch()`, `XMLHttpRequest`, or loading external tracking images).

To enforce complete network isolation, a restrictive **Content Security Policy (CSP)** `<meta>` tag is systematically injected into the `<head>` of all generated HTML artifacts:

```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'none';
  style-src 'unsafe-inline';
  img-src data:;
  font-src data:;
  connect-src 'none';
  form-action 'none';
  base-uri 'none';
  script-src 'none';  /* or 'unsafe-inline' only when scripts are required */
">
```

### Directive Breakdown & Network Capabilities:

| Directive | Value | Purpose |
|-----------|-------|---------|
| `default-src` | `'none'` | Default fallback that denies all resource loading. |
| `style-src` | `'unsafe-inline'` | Permits embedded styling (`<style>` tags) for self-contained aesthetic widgets. |
| `img-src` | `data:` | Blocks external images, tracking pixels, and CDNs; only permits embedded base64 `data:` URIs. |
| `font-src` | `data:` | Blocks external font CDNs (e.g. Google Fonts); permits embedded font data. |
| `connect-src` | `'none'` | **Blocks all network requests**: `fetch()`, `XMLHttpRequest`, `WebSocket`, and `EventSource` cannot transmit data outside the sandbox. |
| `form-action` | `'none'` | Prevents form submissions to external endpoints. |
| `base-uri` | `'none'` | Prevents altering the document base URL. |
| `script-src` | `'none'` (static) or `'unsafe-inline'` (script) | For static HTML, scripts are blocked at the CSP level; for interactive HTML, inline script execution is permitted but strictly confined. |

---

## 6. Verification and Automated Testing

Security controls are verified through multi-tier automated testing:

1. **Frontend DOM & Browser Simulation (`frontend/test/security.test.js`)**:
   - Tests DOMPurify against real DOM injection attempts (verifying `<script>`, `<iframe>`, `<form>`, and `onerror` are purged from the DOM).
   - Tests iframe sandbox configuration against DOM elements (verifying empty string for static, `allow-scripts` for interactive, and absence of `allow-same-origin` or navigation tokens).
   - Tests CSP injection and parsing via JSDOM to ensure directives are present and properly configured.

2. **Backend Pipeline Tests (`backend/tests/test_artifacts.py`)**:
   - Tests `ArtifactSkill` CSP injection logic.
   - Tests replacement of weak CSP tags with strict security policies.
   - Tests database persistence, retrieval, and message linking via `ArtifactService`.
