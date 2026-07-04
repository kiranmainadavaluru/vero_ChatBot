import { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:5000/api'

// ─────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────
async function apiListSessions() {
  const res = await fetch(`${API_BASE}/sessions`)
  if (!res.ok) throw new Error('Could not load your conversations.')
  return res.json()
}

async function apiCreateSession() {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  if (!res.ok) throw new Error('Could not start a new chat.')
  return res.json()
}

async function apiGetMessages(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`)
  if (!res.ok) throw new Error('Could not load this conversation.')
  return res.json()
}

async function apiDeleteSession(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) throw new Error('Could not delete this conversation.')
}

async function apiListDocuments() {
  const res = await fetch(`${API_BASE}/documents`)
  if (!res.ok) throw new Error('Could not load documents.')
  return res.json()
}

async function apiUploadFiles(files) {
  const formData = new FormData()
  for (const f of files) formData.append('files', f)
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData })
  const data = await res.json()
  if (!res.ok && (!data.uploaded || data.uploaded.length === 0) && (!data.errors || data.errors.length === 0)) {
    throw new Error(data.error || 'Upload failed.')
  }
  return data // { uploaded: [...], errors: [...] }
}

async function apiDeleteDocument(documentId) {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Could not delete this document.')
}

function toFrontendMessage(m) {
  return {
    role: m.role,
    content: m.content,
    sources: m.sources || undefined,
    retrieval: m.retrieval || undefined,
  }
}

function titleFromQuestion(question) {
  const trimmed = question.trim()
  // matches the backend's own truncation (_title_from_question in app.py)
  // so the locally-optimistic title never visibly differs from the stored one
  return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed
}

// ─────────────────────────────────────────────────────────────
// Evidence + retrieval display
// ─────────────────────────────────────────────────────────────
function EvidenceCard({ chunk }) {
  const relevance = Math.max(0, Math.min(1, 1 - chunk.distance))
  return (
    <div className="evidence-card">
      <div className="evidence-meta">
        <span className="evidence-index">
          {chunk.filename}{chunk.page_number > 0 ? ` · p.${chunk.page_number}` : ''} · chunk {chunk.chunk_index}
        </span>
        <div className="evidence-bar-track">
          <div className="evidence-bar-fill" style={{ width: `${relevance * 100}%` }} />
        </div>
        <span className="evidence-distance">{chunk.distance.toFixed(3)}</span>
      </div>
      <p className="evidence-text">{chunk.content}</p>
    </div>
  )
}

function RetrievalBadge({ retrieval }) {
  const [showCandidates, setShowCandidates] = useState(false)
  if (!retrieval || !retrieval.filename) return null

  const isAuto = retrieval.mode === 'auto_routed'
  const candidates = retrieval.candidate_documents || []

  return (
    <div className="retrieval-block">
      <button
        className="retrieval-badge"
        onClick={() => isAuto && candidates.length > 1 && setShowCandidates((s) => !s)}
        disabled={!isAuto || candidates.length <= 1}
      >
        <span className="retrieval-dot" />
        answered from <strong>{retrieval.filename}</strong>
        {isAuto && candidates.length > 1 && (
          <span className={`chevron ${showCandidates ? 'open' : ''}`}>›</span>
        )}
      </button>

      {showCandidates && (
        <div className="candidate-list">
          {candidates.map((c) => {
            const relevance = Math.max(0, Math.min(1, 1 / (1 + c.best_distance)))
            const isWinner = c.document_id === retrieval.document_id
            return (
              <div className={`candidate-row ${isWinner ? 'winner' : ''}`} key={c.document_id}>
                <span className="candidate-name">{c.filename}</span>
                <div className="evidence-bar-track">
                  <div className="evidence-bar-fill" style={{ width: `${relevance * 100}%` }} />
                </div>
                {isWinner && <span className="candidate-tag">chosen</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Message({ role, content, error }) {
  if (role === 'user') {
    return (
      <div className="message-row user">
        <div className="bubble user-bubble">{content}</div>
      </div>
    )
  }

  return (
    <div className="message-row assistant">
      <div className={`bubble assistant-bubble ${error ? 'error-bubble' : ''}`}>
        <p className="answer-text">{content}</p>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Documents panel: upload, list, delete
// (kept for reference but no longer rendered)
// ─────────────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
function DocumentsPanel({ documents, loading, uploading, uploadErrors, onUpload, onDelete }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    onUpload(e.dataTransfer.files)
  }

  return (
    <div className="documents-section">
      <span className="eyebrow">documents</span>

      <div
        className={`dropzone ${dragOver ? 'drag-over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => { onUpload(e.target.files); e.target.value = '' }}
        />
        {uploading ? 'Uploading…' : 'Drop files or click to upload'}
      </div>

      {uploadErrors.length > 0 && (
        <div className="upload-errors">
          {uploadErrors.map((e, i) => (
            <p key={i} className="upload-error-item">{e.filename}: {e.error}</p>
          ))}
        </div>
      )}

      <div className="document-list">
        {loading && <p className="session-empty">Loading…</p>}
        {!loading && documents.length === 0 && <p className="session-empty">No documents yet.</p>}
        {documents.map((d) => (
          <div className="document-item" key={d.document_id}>
            <div className="document-info">
              <span className="document-name" title={d.filename}>{d.filename}</span>
              <span className="document-meta">{d.file_type} · {d.chunk_count} chunks</span>
            </div>
            <button
              className="session-delete"
              onClick={() => onDelete(d.document_id)}
              aria-label="Delete document"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Sidebar: chat history, draggable to either edge of the screen
// ─────────────────────────────────────────────────────────────
function Sidebar({
  sessions, activeId, onSelect, onCreate, onDelete, dragPreview, onDragStart, mobileOpen,
}) {
  return (
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="sidebar-top">
        <span className="eyebrow">history</span>
        <button className="new-chat-btn" onClick={onCreate}>+ New chat</button>
      </div>

      <div className="session-list">
        {sessions.length === 0 && <p className="session-empty">No conversations yet.</p>}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`session-item ${s.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(s.id)}
          >
            <span className="session-title">{s.title}</span>
            <button
              className="session-delete"
              onClick={(e) => { e.stopPropagation(); onDelete(s.id) }}
              aria-label="Delete conversation"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        className={`drag-handle ${dragPreview ? 'dragging' : ''}`}
        onPointerDown={onDragStart}
        aria-label="Drag to move panel to the other side"
        title="Drag to move this panel"
      >
        <span className="grip-dot" /><span className="grip-dot" /><span className="grip-dot" />
      </button>
    </aside>
  )
}

// ─────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────
export default function App() {
  const [sessions, setSessions] = useState([])   // [{id, title, messages: null|array, created_at, updated_at}]
  const [activeId, setActiveId] = useState(null)
  const [input, setInput] = useState('')
  const [loadingSessionId, setLoadingSessionId] = useState(null)   // sending a question
  const [messagesLoadingId, setMessagesLoadingId] = useState(null) // fetching a session's messages
  const [initializing, setInitializing] = useState(true)
  const [bootError, setBootError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [side, setSide] = useState('left')
  const [dragPreview, setDragPreview] = useState(null)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadNotice, setUploadNotice] = useState(null) // { type: 'ok'|'err', text }
  const scrollRef = useRef(null)
  const isDraggingRef = useRef(false)
  const attachInputRef = useRef(null)

  const activeSession = sessions.find((s) => s.id === activeId) ?? null
  const loading = loadingSessionId === activeId
  const messagesLoading = messagesLoadingId === activeId

  // ── Load existing conversations on mount instead of starting empty ──
  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        const list = await apiListSessions()
        if (cancelled) return

        if (list.length === 0) {
          const fresh = await apiCreateSession()
          if (cancelled) return
          setSessions([{ ...fresh, messages: [] }])
          setActiveId(fresh.id)
        } else {
          setSessions(list.map((s) => ({ ...s, messages: null })))
          setActiveId(list[0].id)
          await loadMessagesFor(list[0].id)
        }
      } catch (err) {
        if (!cancelled) setBootError(err.message)
      } finally {
        if (!cancelled) setInitializing(false)
      }
    }

    bootstrap()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [activeSession?.messages, loading, activeId])

  async function handleUpload(fileList) {
    const files = Array.from(fileList || [])
    if (files.length === 0) return
    setUploading(true)
    setUploadNotice(null)
    try {
      const result = await apiUploadFiles(files)
      const okCount = (result.uploaded || []).length
      const errCount = (result.errors || []).length
      if (okCount > 0 && errCount === 0) {
        setUploadNotice({ type: 'ok', text: `Uploaded ${okCount} file${okCount === 1 ? '' : 's'}.` })
      } else if (okCount > 0 && errCount > 0) {
        setUploadNotice({ type: 'err', text: `Uploaded ${okCount}, ${errCount} failed.` })
      } else if (errCount > 0) {
        setUploadNotice({ type: 'err', text: `Upload failed: ${result.errors[0].error}` })
      }
      setTimeout(() => setUploadNotice(null), 4000)
    } catch (err) {
      setUploadNotice({ type: 'err', text: err.message })
      setTimeout(() => setUploadNotice(null), 4000)
    } finally {
      setUploading(false)
    }
  }

  async function loadMessagesFor(sessionId) {
    setMessagesLoadingId(sessionId)
    try {
      const raw = await apiGetMessages(sessionId)
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, messages: raw.map(toFrontendMessage) } : s))
      )
    } catch (err) {
      setActionError(err.message)
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? { ...s, messages: [] } : s)))
    } finally {
      setMessagesLoadingId((id) => (id === sessionId ? null : id))
    }
  }

  function updateSessionMessages(sessionId, updater) {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, messages: updater(s.messages || []) } : s))
    )
  }

  async function handleCreate() {
    try {
      const fresh = await apiCreateSession()
      setSessions((prev) => [{ ...fresh, messages: [] }, ...prev])
      setActiveId(fresh.id)
      setInput('')
      setMobileSidebarOpen(false)
    } catch (err) {
      setActionError(err.message)
    }
  }

  function handleSelect(id) {
    setActiveId(id)
    setMobileSidebarOpen(false)
    const session = sessions.find((s) => s.id === id)
    if (session && session.messages === null) {
      loadMessagesFor(id)
    }
  }

  async function handleDelete(id) {
    try {
      await apiDeleteSession(id)
    } catch (err) {
      setActionError(err.message)
      return
    }

    const remaining = sessions.filter((s) => s.id !== id)

    if (remaining.length === 0) {
      await handleCreate()
      return
    }

    setSessions(remaining)
    if (id === activeId) {
      const next = remaining[0]
      setActiveId(next.id)
      if (next.messages === null) loadMessagesFor(next.id)
    }
  }

  async function sendQuestion(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || loadingSessionId || !activeId) return

    const targetId = activeId
    const isFirstMessage = !activeSession?.messages || activeSession.messages.length === 0

    updateSessionMessages(targetId, (msgs) => [...msgs, { role: 'user', content: question }])
    if (isFirstMessage) {
      setSessions((prev) =>
        prev.map((s) => (s.id === targetId ? { ...s, title: titleFromQuestion(question) } : s))
      )
    }
    setInput('')
    setLoadingSessionId(targetId)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: targetId })
      })
      const data = await res.json()

      if (!res.ok) {
        updateSessionMessages(targetId, (msgs) => [
          ...msgs,
          { role: 'assistant', content: data.error || 'Something went wrong.', error: true }
        ])
      } else {
        updateSessionMessages(targetId, (msgs) => [
          ...msgs,
          { role: 'assistant', content: data.answer, sources: data.sources, retrieval: data.retrieval }
        ])
        // Backend already bumped updated_at via touch_session - mirror that
        // ordering locally so the sidebar doesn't need a full re-fetch.
        setSessions((prev) => {
          const idx = prev.findIndex((s) => s.id === targetId)
          if (idx <= 0) return prev
          const copy = [...prev]
          const [item] = copy.splice(idx, 1)
          copy.unshift(item)
          return copy
        })
      }
    } catch (err) {
      updateSessionMessages(targetId, (msgs) => [
        ...msgs,
        {
          role: 'assistant',
          content: `Couldn't reach the backend. Is it running at ${API_BASE}?`,
          error: true
        }
      ])
    } finally {
      setLoadingSessionId(null)
    }
  }

  // ── Drag-to-reposition the sidebar ──────────────────────────
  const handlePointerMove = useCallback((e) => {
    if (!isDraggingRef.current) return
    const midpoint = window.innerWidth / 2
    setDragPreview(e.clientX < midpoint ? 'left' : 'right')
  }, [])

  const handlePointerUp = useCallback((e) => {
    if (!isDraggingRef.current) return
    isDraggingRef.current = false
    const midpoint = window.innerWidth / 2
    setSide(e.clientX < midpoint ? 'left' : 'right')
    setDragPreview(null)
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', handlePointerUp)
  }, [handlePointerMove])

  function handleDragStart() {
    isDraggingRef.current = true
    setDragPreview(side)
    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
  }

  // ── Boot states ──────────────────────────────────────────────
  if (initializing) {
    return (
      <div className="boot-screen">
        <div className="thinking-standalone">
          <span className="dot" /><span className="dot" /><span className="dot" />
        </div>
        <p className="boot-text">Loading your conversations…</p>
      </div>
    )
  }

  if (bootError) {
    return (
      <div className="boot-screen">
        <p className="boot-text error-text">Couldn't reach the backend.</p>
        <p className="boot-hint">{bootError} Is it running at {API_BASE}?</p>
        <button className="retry-btn" onClick={() => window.location.reload()}>Retry</button>
      </div>
    )
  }

  return (
    <div className="workspace" data-side={side}>
      {dragPreview && (
        <>
          <div className={`dock-zone dock-left ${dragPreview === 'left' ? 'active' : ''}`} />
          <div className={`dock-zone dock-right ${dragPreview === 'right' ? 'active' : ''}`} />
        </>
      )}

      {mobileSidebarOpen && (
        <div className="mobile-backdrop" onClick={() => setMobileSidebarOpen(false)} />
      )}

      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onDelete={handleDelete}
        dragPreview={dragPreview}
        onDragStart={handleDragStart}
        mobileOpen={mobileSidebarOpen}
      />

      <main className="chat-shell">
        <header className="header">
          <button
            className="mobile-menu-btn"
            onClick={() => setMobileSidebarOpen((o) => !o)}
            aria-label="Toggle chat history"
          >
            ☰
          </button>
          <span className="eyebrow">your document assistant</span>
          <h1>Vero</h1>
        </header>

        {actionError && (
          <div className="action-banner">
            {actionError}
            <button onClick={() => setActionError(null)} aria-label="Dismiss">×</button>
          </div>
        )}

        <div className="chat-area" ref={scrollRef}>
          <div className="chat-inner">
            {messagesLoading && (
              <div className="empty-state">
                <p>Loading conversation…</p>
              </div>
            )}

            {!messagesLoading && activeSession?.messages?.length === 0 && (
              <div className="empty-state">
                <p>Hi, I'm Vero.</p>
                <p className="empty-hint">Attach a document and ask me anything about it.</p>
              </div>
            )}

            {!messagesLoading &&
              activeSession?.messages?.map((m, i) => <Message key={i} {...m} />)}

            {loading && (
              <div className="message-row assistant">
                <div className="bubble assistant-bubble thinking">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            )}
          </div>
        </div>

        {uploadNotice && (
          <div className={`upload-toast ${uploadNotice.type === 'err' ? 'err' : 'ok'}`}>
            {uploadNotice.text}
          </div>
        )}

        <form className="input-bar" onSubmit={sendQuestion}>
          <div className="chat-inner input-inner">
            <div className={`input-shell ${loading ? 'is-disabled' : ''}`}>
              <input
                ref={attachInputRef}
                type="file"
                multiple
                hidden
                onChange={(e) => { handleUpload(e.target.files); e.target.value = '' }}
              />
              <button
                type="button"
                className="icon-btn attach-btn"
                onClick={() => attachInputRef.current?.click()}
                disabled={loading || uploading}
                aria-label="Attach a document"
                title="Attach a document"
              >
                {uploading ? (
                  <span className="mini-spinner" />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                )}
              </button>
              <input
                type="text"
                className="text-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask Vero about your documents…"
                disabled={loading}
              />
              <button
                type="submit"
                className="icon-btn send-btn"
                disabled={loading || !input.trim()}
                aria-label="Send message"
                title="Send"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  )
}