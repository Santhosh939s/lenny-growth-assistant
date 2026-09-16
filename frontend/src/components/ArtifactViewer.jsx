import React, { useState } from 'react';
import {
  renderSanitizedMarkdown,
  prepareHtmlArtifact,
  getIframeSandbox,
  requiresScript,
} from '../utils/security';
import './ArtifactViewer.css';

export default function ArtifactViewer({
  artifact,
  allArtifacts = [],
  onSelectArtifact,
  onClose,
}) {
  const [viewMode, setViewMode] = useState('rendered'); // 'rendered' | 'code'
  const [copied, setCopied] = useState(false);

  if (!artifact) {
    return (
      <aside className="artifact-viewer empty" aria-label="Artifact Viewer">
        <div className="artifact-placeholder">
          <div className="placeholder-icon">📄</div>
          <h3>No Artifact Selected</h3>
          <p>Generate an artifact in the chat or select one to preview.</p>
        </div>
      </aside>
    );
  }

  const isHtml = artifact.type === 'html';
  const hasScript = isHtml && requiresScript(artifact.content);
  const sandboxPolicy = isHtml ? getIframeSandbox(artifact.content) : '';
  const preparedHtml = isHtml ? prepareHtmlArtifact(artifact.content) : '';
  const sanitizedMarkdown = !isHtml ? renderSanitizedMarkdown(artifact.content) : '';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  return (
    <aside className="artifact-viewer" aria-label="Artifact Viewer">
      {/* Top Header */}
      <div className="artifact-header">
        <div className="artifact-header-left">
          <span className={`artifact-badge ${artifact.type}`}>
            {artifact.type.toUpperCase()}
          </span>
          <h2 className="artifact-title" title={artifact.title}>
            {artifact.title}
          </h2>
        </div>

        <div className="artifact-header-actions">
          {/* View Mode Toggle */}
          <div className="mode-toggle-group">
            <button
              className={`mode-btn ${viewMode === 'rendered' ? 'active' : ''}`}
              onClick={() => setViewMode('rendered')}
              title="Rendered Preview"
            >
              Preview
            </button>
            <button
              className={`mode-btn ${viewMode === 'code' ? 'active' : ''}`}
              onClick={() => setViewMode('code')}
              title="Raw Code View"
            >
              Code
            </button>
          </div>

          {/* Copy Button */}
          <button
            className={`action-btn copy-btn ${copied ? 'copied' : ''}`}
            onClick={handleCopy}
            title="Copy Content"
          >
            {copied ? '✓ Copied' : 'Copy'}
          </button>

          {/* Close Button */}
          <button
            className="action-btn close-btn"
            onClick={onClose}
            title="Close Artifact Viewer"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Security Status Bar */}
      <div className="security-status-bar">
        {!isHtml ? (
          <span className="sec-tag safe">
            🛡️ Sanitized with DOMPurify (Scripts, Iframes & Event Handlers Blocked)
          </span>
        ) : hasScript ? (
          <span className="sec-tag notice">
            🔒 Sandboxed (sandbox="allow-scripts" | Same-Origin Blocked | CSP connect-src 'none')
          </span>
        ) : (
          <span className="sec-tag safe">
            🔒 Sandboxed (Least-Privilege sandbox="" | No Scripts | CSP Restrictive)
          </span>
        )}
      </div>

      {/* Multiple Artifacts Switcher (if more than 1 artifact exists) */}
      {allArtifacts && allArtifacts.length > 1 && (
        <div className="artifact-tabs-bar">
          <span className="tabs-label">Artifacts ({allArtifacts.length}):</span>
          <div className="tabs-list">
            {allArtifacts.map((art) => (
              <button
                key={art.id}
                className={`artifact-tab ${art.id === artifact.id ? 'active' : ''}`}
                onClick={() => onSelectArtifact && onSelectArtifact(art)}
                title={art.title}
              >
                <span className={`tab-dot ${art.type}`}></span>
                <span className="tab-title">{art.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Artifact Main Body */}
      <div className="artifact-body">
        {viewMode === 'code' ? (
          <div className="raw-code-container">
            <pre className="raw-code">
              <code>{artifact.content}</code>
            </pre>
          </div>
        ) : isHtml ? (
          <div className="iframe-container">
            <iframe
              title={artifact.title}
              srcDoc={preparedHtml}
              sandbox={sandboxPolicy}
              className="artifact-iframe"
            />
          </div>
        ) : (
          <div
            className="artifact-markdown-content"
            dangerouslySetInnerHTML={{ __html: sanitizedMarkdown }}
          />
        )}
      </div>
    </aside>
  );
}
