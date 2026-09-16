import { useState, useEffect, useRef } from 'react'
import ArtifactViewer from './components/ArtifactViewer'
import { renderSanitizedMarkdown } from './utils/security'
import './App.css'

const STARTER_PROMPTS = [
  {
    icon: "🎯",
    tag: "Lenny RAG",
    title: "Product-Market Fit",
    prompt: "What did Lenny's guests say about product-market fit and knowing when you have it?"
  },
  {
    icon: "🚀",
    tag: "Ship 30 Skill",
    title: "Viral Growth Loops",
    prompt: "Write a Ship 30 for 30 article on user retention loops vs acquisition funnels."
  },
  {
    icon: "📊",
    tag: "Markdown Artifact",
    title: "Cohort Retention Guide",
    prompt: "Create a brief Markdown document about SaaS cohort retention benchmarks."
  },
  {
    icon: "💳",
    tag: "HTML Artifact",
    title: "Pricing Card Component",
    prompt: "Create an HTML pricing card with embedded CSS and modern styling."
  }
]

function App() {
  const [health, setHealth] = useState({ status: 'checking...', provider: 'ollama', database: 'connected' })
  const [sessions, setSessions] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  // Artifact State
  const [sessionArtifacts, setSessionArtifacts] = useState([])
  const [activeArtifact, setActiveArtifact] = useState(null)
  const [isViewerOpen, setIsViewerOpen] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const API_SESSIONS = 'http://127.0.0.1:8000/api/sessions'
  const API_ARTIFACTS = 'http://127.0.0.1:8000/api/artifacts'

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then(res => res.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({ status: 'offline', provider: 'unknown', database: 'disconnected' }))

    fetchSessions()
  }, [])

  useEffect(() => {
    if (currentSession) {
      fetchSessionMessages(currentSession.id)
      fetchSessionArtifacts(currentSession.id)
    } else {
      setMessages([])
      setSessionArtifacts([])
      setActiveArtifact(null)
      setIsViewerOpen(false)
    }
  }, [currentSession])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const fetchSessions = async () => {
    try {
      const res = await fetch(API_SESSIONS)
      const data = await res.json()
      setSessions(data)
      if (data.length > 0 && !currentSession) {
        setCurrentSession(data[0])
      }
    } catch (e) {
      console.error('Failed to fetch sessions', e)
    }
  }

  const fetchSessionMessages = async (id) => {
    try {
      const res = await fetch(`${API_SESSIONS}/${id}`)
      const data = await res.json()
      setMessages(data.messages || [])
    } catch (e) {
      console.error('Failed to fetch messages', e)
    }
  }

  const fetchSessionArtifacts = async (sessionId) => {
    try {
      const res = await fetch(`${API_ARTIFACTS}/session/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setSessionArtifacts(data)
        if (data.length > 0) {
          setActiveArtifact(data[0])
        } else {
          setActiveArtifact(null)
        }
      }
    } catch (e) {
      console.error('Failed to fetch session artifacts', e)
    }
  }

  const createNewSession = async () => {
    try {
      const res = await fetch(API_SESSIONS + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Growth Chat' })
      })
      const newSess = await res.json()
      setSessions([newSess, ...sessions])
      setCurrentSession(newSess)
      setMessages([])
      setActiveArtifact(null)
      setIsViewerOpen(false)
      inputRef.current?.focus()
    } catch (e) {
      console.error('Failed to create session', e)
    }
  }

  const deleteSession = async (id, e) => {
    e.stopPropagation()
    try {
      await fetch(`${API_SESSIONS}/${id}`, { method: 'DELETE' })
      const updated = sessions.filter(s => s.id !== id)
      setSessions(updated)
      if (currentSession?.id === id) {
        setCurrentSession(updated.length > 0 ? updated[0] : null)
      }
    } catch (err) {
      console.error('Failed to delete session', err)
    }
  }

  const openArtifactById = async (artifactId) => {
    const found = sessionArtifacts.find(a => a.id === artifactId)
    if (found) {
      setActiveArtifact(found)
      setIsViewerOpen(true)
      return
    }

    try {
      const res = await fetch(`${API_ARTIFACTS}/${artifactId}`)
      if (res.ok) {
        const data = await res.json()
        setActiveArtifact(data)
        setSessionArtifacts(prev => [data, ...prev.filter(a => a.id !== data.id)])
        setIsViewerOpen(true)
      }
    } catch (err) {
      console.error('Failed to open artifact:', err)
    }
  }

  const sendMessage = async (overrideContent) => {
    const contentToSend = (typeof overrideContent === 'string' ? overrideContent : inputValue).trim()
    if (!contentToSend) return

    let activeSession = currentSession
    if (!activeSession) {
      try {
        const res = await fetch(API_SESSIONS + '/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: contentToSend.slice(0, 36) + '...' })
        })
        activeSession = await res.json()
        setSessions([activeSession, ...sessions])
        setCurrentSession(activeSession)
      } catch (e) {
        console.error('Failed to create session on message', e)
        return
      }
    }

    const userMessage = { role: 'user', content: contentToSend }
    setMessages(prev => [...prev, { ...userMessage, id: 'temp-' + Date.now(), created_at: new Date().toISOString() }])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await fetch(`${API_SESSIONS}/${activeSession.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userMessage)
      })
      const agentRes = await res.json()

      if (agentRes.provider) {
        setHealth(prev => ({ ...prev, provider: agentRes.provider }))
      }

      if (agentRes.artifact) {
        setActiveArtifact(agentRes.artifact)
        setSessionArtifacts(prev => [agentRes.artifact, ...prev.filter(a => a.id !== agentRes.artifact.id)])
        setIsViewerOpen(true)
      }

      await fetchSessionMessages(activeSession.id)
    } catch (e) {
      console.error('Failed to send message', e)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <header className="header">
        <div className="header-left">
          <div className="brand-logo">
            <span className="brand-icon">⚡</span>
            <div className="brand-text-block">
              <h1 className="brand-title">Lenny Growth Assistant</h1>
              <span className="brand-subtitle">AI Knowledge &amp; Execution Agent</span>
            </div>
          </div>
          {currentSession && (
            <div className="current-session-tag" title={currentSession.title}>
              <span className="session-tag-icon">💬</span>
              <span className="session-tag-label">{currentSession.title || 'Conversation'}</span>
            </div>
          )}
        </div>

        <div className="header-right">
          {sessionArtifacts.length > 0 && (
            <button
              className={`artifacts-toggle-btn ${isViewerOpen ? 'active' : ''}`}
              onClick={() => setIsViewerOpen(prev => !prev)}
            >
              <span className="btn-icon">⚡</span>
              <span>Artifacts ({sessionArtifacts.length})</span>
              <span className="btn-badge">{isViewerOpen ? 'Hide' : 'View'}</span>
            </button>
          )}

          <div className="status-badge" title={`LLM: ${health.provider} | DB: ${health.database} | Status: ${health.status}`}>
            <span className={`status-dot ${health.status === 'healthy' ? 'online' : 'offline'}`}></span>
            <span className="status-item provider">{health.provider}</span>
            <span className="status-divider">•</span>
            <span className="status-item db">PostgreSQL</span>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="main-content">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-top">
            <button className="new-chat-btn" onClick={createNewSession}>
              <span className="btn-plus">+</span>
              <span>New Conversation</span>
            </button>
          </div>

          <div className="sidebar-section-header">
            <span>Conversations</span>
            <span className="session-count-badge">{sessions.length}</span>
          </div>

          <div className="session-list">
            {sessions.map(s => (
              <div
                key={s.id}
                className={`session-item ${currentSession?.id === s.id ? 'active' : ''}`}
                onClick={() => setCurrentSession(s)}
              >
                <div className="session-item-left">
                  <span className="session-icon">💬</span>
                  <span className="session-title" title={s.title}>{s.title || 'Untitled Chat'}</span>
                </div>
                <button
                  className="delete-btn"
                  title="Delete conversation"
                  onClick={(e) => deleteSession(s.id, e)}
                >
                  ✕
                </button>
              </div>
            ))}
            {sessions.length === 0 && (
              <div className="no-sessions">
                <p>No conversations yet.</p>
                <small>Click "New Conversation" to begin.</small>
              </div>
            )}
          </div>

          <div className="sidebar-footer">
            <div className="kb-info">
              <span className="kb-dot"></span>
              <span>10,000+ chunks indexed</span>
            </div>
          </div>
        </aside>

        {/* Chat Area */}
        <section className={`chat-area ${isViewerOpen && activeArtifact ? 'with-viewer' : ''}`}>
          <div className="message-history">
            {messages.length === 0 ? (
              <div className="empty-hero">
                <div className="hero-badge">
                  <span className="hero-badge-dot"></span>
                  Grounded in Lenny Rachitsky's Podcast
                </div>
                <h2 className="hero-title">What growth challenge are you solving today?</h2>
                <p className="hero-desc">
                  Ask deep questions grounded in hundreds of expert interviews, draft structured Ship 30 articles, or generate interactive UI artifacts.
                </p>

                <div className="starter-grid">
                  {STARTER_PROMPTS.map((card, idx) => (
                    <div
                      key={idx}
                      className="starter-card"
                      onClick={() => sendMessage(card.prompt)}
                    >
                      <div className="starter-card-header">
                        <span className="starter-card-icon">{card.icon}</span>
                        <span className="starter-card-tag">{card.tag}</span>
                      </div>
                      <h3 className="starter-card-title">{card.title}</h3>
                      <p className="starter-card-prompt">{card.prompt}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={msg.id || i} className={`message-row ${msg.role}`}>
                  <div className="message-avatar">
                    {msg.role === 'user' ? '👤' : '⚡'}
                  </div>

                  <div className="message-bubble">
                    <div className="bubble-header">
                      <span className="sender-name">{msg.role === 'user' ? 'You' : 'Lenny Assistant'}</span>
                      {msg.created_at && (
                        <span className="message-time">
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>

                    {msg.role === 'assistant' ? (
                      <div
                        className="bubble-content markdown-rendered"
                        dangerouslySetInnerHTML={{ __html: renderSanitizedMarkdown(msg.content) }}
                      />
                    ) : (
                      <div className="bubble-content user-text">{msg.content}</div>
                    )}

                    {/* Embedded Artifact Callout */}
                    {msg.meta && msg.meta.artifact_id && (
                      <div className="artifact-callout-card">
                        <div className="artifact-callout-info">
                          <span className="artifact-callout-icon">⚡</span>
                          <div className="artifact-callout-texts">
                            <div className="artifact-callout-title">
                              {msg.meta.artifact_title || 'Generated Artifact'}
                            </div>
                            <span className={`artifact-callout-tag ${msg.meta.artifact_type || 'markdown'}`}>
                              {(msg.meta.artifact_type || 'ARTIFACT').toUpperCase()}
                            </span>
                          </div>
                        </div>
                        <button
                          className="open-artifact-btn"
                          onClick={() => openArtifactById(msg.meta.artifact_id)}
                        >
                          {activeArtifact?.id === msg.meta.artifact_id && isViewerOpen
                            ? 'Viewing Beside Chat ✓'
                            : 'Open Artifact Viewer ↗'}
                        </button>
                      </div>
                    )}

                    {/* Podcast Grounded Sources */}
                    {msg.meta && msg.meta.sources && msg.meta.sources.length > 0 && (
                      <div className="sources-card">
                        <div className="sources-header">
                          <span className="sources-header-icon">🎙️</span>
                          <span className="sources-header-title">
                            Grounded in Lenny's Podcast ({msg.meta.sources.length} episodes cited)
                          </span>
                        </div>
                        <div className="sources-list">
                          {msg.meta.sources.map((src, idx) => (
                            <div key={idx} className="source-item">
                              <div className="source-meta">
                                <span className="source-guest">{src.guest}</span>
                                <span className="source-title" title={src.title}>"{src.title}"</span>
                              </div>
                              {src.youtube_url && (
                                <a
                                  href={src.youtube_url}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  className="source-link"
                                >
                                  Watch ↗
                                </a>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isLoading && (
              <div className="message-row assistant">
                <div className="message-avatar">⚡</div>
                <div className="message-bubble loading-bubble">
                  <div className="typing-indicator">
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </div>
                  <span className="loading-text">Searching Lenny's podcast archives &amp; reasoning...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Floating Prompt Bar */}
          <div className="input-container">
            <div className="input-bar">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder="Ask about PMF, growth loops, or ask for an artifact (e.g. 'Create an HTML pricing card')..."
                disabled={isLoading}
              />
              <button
                className="send-button"
                onClick={() => sendMessage()}
                disabled={isLoading || !inputValue.trim()}
                title="Send message (Enter)"
              >
                <span className="send-arrow">↑</span>
              </button>
            </div>
            <div className="input-footer-note">
              <span>Verified against Lenny's transcript database</span>
              <span>•</span>
              <span>Press <kbd>Enter ↵</kbd> to submit</span>
            </div>
          </div>
        </section>

        {/* Dedicated Split-Screen Artifact Viewer */}
        {isViewerOpen && activeArtifact && (
          <ArtifactViewer
            artifact={activeArtifact}
            allArtifacts={sessionArtifacts}
            onSelectArtifact={(art) => setActiveArtifact(art)}
            onClose={() => setIsViewerOpen(false)}
          />
        )}
      </main>
    </div>
  )
}

export default App
