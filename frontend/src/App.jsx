import { useState, useEffect, useRef } from 'react'
import ArtifactViewer from './components/ArtifactViewer'
import './App.css'

function App() {
  const [health, setHealth] = useState({ status: 'checking...', provider: 'unknown', database: 'unknown' })
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

  const API_SESSIONS = 'http://127.0.0.1:8000/api/sessions'
  const API_ARTIFACTS = 'http://127.0.0.1:8000/api/artifacts'

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then(res => res.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({ status: 'offline', provider: 'unknown', database: 'unknown' }))

    fetchSessions()
  }, [])

  useEffect(() => {
    if (currentSession) {
      fetchSessionMessages(currentSession.id)
      fetchSessionArtifacts(currentSession.id)
    } else {
      setSessionArtifacts([])
      setActiveArtifact(null)
      setIsViewerOpen(false)
    }
  }, [currentSession])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
      setMessages(data.messages)
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
          // Default active artifact to the newest one
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
        body: JSON.stringify({ title: 'New Conversation' })
      })
      const newSess = await res.json()
      setSessions([newSess, ...sessions])
      setCurrentSession(newSess)
      setActiveArtifact(null)
      setIsViewerOpen(false)
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
        if (updated.length === 0) {
          setMessages([])
          setActiveArtifact(null)
          setIsViewerOpen(false)
        }
      }
    } catch (err) {
      console.error('Failed to delete', err)
    }
  }

  const openArtifactById = async (artifactId) => {
    // Check if already in sessionArtifacts list
    const found = sessionArtifacts.find(a => a.id === artifactId)
    if (found) {
      setActiveArtifact(found)
      setIsViewerOpen(true)
      return
    }

    // Otherwise fetch directly
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

  const sendMessage = async () => {
    if (!inputValue.trim() || !currentSession) return

    const userMessage = { role: 'user', content: inputValue }
    // Optimistic update
    setMessages(prev => [...prev, { ...userMessage, id: 'temp-id', created_at: new Date().toISOString() }])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await fetch(`${API_SESSIONS}/${currentSession.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userMessage)
      })
      const agentRes = await res.json()

      if (agentRes.provider) {
        setHealth(prev => ({ ...prev, provider: agentRes.provider }))
      }

      // If an artifact was created with this response, select and display it in the viewer
      if (agentRes.artifact) {
        setActiveArtifact(agentRes.artifact)
        setSessionArtifacts(prev => [agentRes.artifact, ...prev.filter(a => a.id !== agentRes.artifact.id)])
        setIsViewerOpen(true)
      }

      await fetchSessionMessages(currentSession.id)
    } catch (e) {
      console.error('Failed to send message', e)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-left">
          <h1>The Lenny Growth Assistant</h1>
        </div>

        <div className="header-right">
          {sessionArtifacts.length > 0 && (
            <button
              className={`artifacts-toggle-btn ${isViewerOpen ? 'active' : ''}`}
              onClick={() => setIsViewerOpen(prev => !prev)}
            >
              📄 Artifacts ({sessionArtifacts.length}) {isViewerOpen ? 'Hide' : 'Show'}
            </button>
          )}

          <div className="status-badge">
            <span className={`status-dot ${health.status === 'healthy' ? 'online' : 'offline'}`}></span>
            <span>API: {health.status} | DB: {health.database} | LLM: {health.provider}</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Sidebar */}
        <div className="sidebar">
          <button className="new-chat-btn" onClick={createNewSession}>
            + New Chat
          </button>

          <div className="session-list">
            {sessions.map(s => (
              <div
                key={s.id}
                className={`session-item ${currentSession?.id === s.id ? 'active' : ''}`}
                onClick={() => setCurrentSession(s)}
              >
                <div className="session-title">{s.title || 'Untitled'}</div>
                <button className="delete-btn" onClick={(e) => deleteSession(s.id, e)}>✕</button>
              </div>
            ))}
            {sessions.length === 0 && <div className="no-sessions">No conversations yet.</div>}
          </div>
        </div>

        {/* Chat Area */}
        <div className={`chat-area ${isViewerOpen && activeArtifact ? 'with-viewer' : ''}`}>
          {currentSession ? (
            <>
              <div className="message-history">
                {messages.length === 0 && (
                  <div className="empty-chat">
                    <p>This is the start of your conversation.</p>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={msg.id || i} className={`message ${msg.role}`}>
                    <div className="message-bubble">
                      <div className="bubble-text">{msg.content}</div>

                      {/* Embedded Artifact Card if generated */}
                      {msg.meta && msg.meta.artifact_id && (
                        <div className="artifact-bubble-card">
                          <div className="artifact-bubble-info">
                            <span className="artifact-bubble-icon">⚡</span>
                            <div className="artifact-bubble-details">
                              <span className="artifact-bubble-title">
                                {msg.meta.artifact_title || 'Generated Artifact'}
                              </span>
                              <span className={`artifact-bubble-tag ${msg.meta.artifact_type || 'markdown'}`}>
                                {(msg.meta.artifact_type || 'ARTIFACT').toUpperCase()}
                              </span>
                            </div>
                          </div>
                          <button
                            className="view-artifact-btn"
                            onClick={() => openArtifactById(msg.meta.artifact_id)}
                          >
                            {activeArtifact?.id === msg.meta.artifact_id && isViewerOpen
                              ? 'Viewing Now'
                              : 'Open Artifact →'}
                          </button>
                        </div>
                      )}

                      {/* Lenny Podcast Citations / Sources */}
                      {msg.meta && msg.meta.sources && msg.meta.sources.length > 0 && (
                        <div className="sources-container">
                          <strong>Grounded in Lenny's Podcast:</strong>
                          <ul>
                            {msg.meta.sources.map((src, idx) => (
                              <li key={idx}>
                                {src.title} (Guest: {src.guest})
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && <div className="message assistant loading">Lenny Assistant is thinking...</div>}
                <div ref={messagesEndRef} />
              </div>

              <div className="input-area">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Ask Lenny about growth, product, or request an artifact (e.g. 'Create an HTML pricing card')..."
                  disabled={isLoading}
                />
                <button onClick={sendMessage} disabled={isLoading || !inputValue.trim()}>
                  Send
                </button>
              </div>
            </>
          ) : (
            <div className="chat-placeholder">
              <p>Select or create a conversation to start.</p>
            </div>
          )}
        </div>

        {/* Dedicated In-App Artifact Viewer */}
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
