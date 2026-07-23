import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_BASE = 'http://127.0.0.1:8000/api'
const TOKEN_KEY = 'vero_token'
const USER_KEY = 'vero_user'

// ─────────────────────────────────────────────────────────────
// Auth storage + fetch wrapper
// ─────────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

function storeAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

// Wraps fetch() with the Authorization header + a shared 401 handler.
// On an expired/invalid token it clears storage and tells the app
// (via a window event) to fall back to the login screen, instead of
// every caller having to check for 401 individually.
async function authFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearAuth()
    window.dispatchEvent(new Event('auth:expired'))
  }
  return res
}

async function apiRegister(email, password, name) {
  let res
  try {
    res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name })
    })
  } catch {
    throw new Error(`Couldn't reach the backend. Is it running at ${API_BASE}?`)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Could not create your account.')
  return data // { token, user }
}

async function apiLogin(email, password) {
  let res
  try {
    res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })
  } catch {
    throw new Error(`Couldn't reach the backend. Is it running at ${API_BASE}?`)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Could not log you in.')
  return data // { token, user }
}

async function apiVerifyEmail(token) {
  let res
  try {
    res = await fetch(`${API_BASE}/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    })
  } catch {
    throw new Error(`Couldn't reach the backend. Is it running at ${API_BASE}?`)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Could not verify this email.')
  return data // { verified, already, user }
}

async function apiResendVerification() {
  const res = await authFetch('/auth/resend-verification', { method: 'POST' })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Could not resend the verification email.')
  return data
}

async function apiMe() {
  const res = await authFetch('/auth/me')
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Could not check your account.')
  return data // user
}

// ─────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────
async function apiListSessions() {
  const res = await authFetch('/sessions')
  if (!res.ok) throw new Error('Could not load your conversations.')
  return res.json()
}

async function apiCreateSession() {
  const res = await authFetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  if (!res.ok) throw new Error('Could not start a new chat.')
  return res.json()
}

async function apiGetMessages(sessionId) {
  const res = await authFetch(`/sessions/${sessionId}/messages`)
  if (!res.ok) throw new Error('Could not load this conversation.')
  return res.json()
}

async function apiDeleteSession(sessionId) {
  const res = await authFetch(`/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) throw new Error('Could not delete this conversation.')
}

async function apiListDocuments() {
  const res = await authFetch('/documents')
  if (!res.ok) throw new Error('Could not load documents.')
  return res.json()
}

async function apiUploadFiles(files) {
  const formData = new FormData()
  for (const f of files) formData.append('files', f)
  const res = await authFetch('/upload', { method: 'POST', body: formData })
  const data = await res.json()
  if (!res.ok && (!data.uploaded || data.uploaded.length === 0) && (!data.errors || data.errors.length === 0)) {
    throw new Error(data.error || 'Upload failed.')
  }
  return data // { uploaded: [...], errors: [...] }
}

async function apiDeleteDocument(documentId) {
  const res = await authFetch(`/documents/${documentId}`, { method: 'DELETE' })
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
  const relevance = Math.max(0, Math.min(1, chunk.score))
  return (
    <div className="evidence-card">
      <div className="evidence-meta">
        <span className="evidence-index">
          {chunk.filename}{chunk.page_number > 0 ? ` · p.${chunk.page_number}` : ''} · chunk {chunk.chunk_index}
        </span>
        <div className="evidence-bar-track">
          <div className="evidence-bar-fill" style={{ width: `${relevance * 100}%` }} />
        </div>
        <span className="evidence-distance">{chunk.score.toFixed(3)}</span>
      </div>
      <p className="evidence-text">{chunk.content}</p>
    </div>
  )
}

function RetrievalBadge({ retrieval }) {
  const [showCandidates, setShowCandidates] = useState(false)
  if (!retrieval) return null

  // Docs-only mode found nothing and refused to answer instead of
  // falling back to general knowledge - the opposite of the branch
  // below, so it needs its own badge rather than falling into the
  // "no filename" -> general-knowledge case.
  if (retrieval.strict_blocked) {
    return (
      <div className="retrieval-block">
        <span className="retrieval-badge docs-only-blocked">
          <span className="retrieval-dot docs-only-blocked-dot" />
          docs only · nothing relevant found, general knowledge not used
        </span>
      </div>
    )
  }

  // No filename means the agent never grounded this answer in a document -
  // either it didn't search at all, or the best match was too weak to trust.
  // Show that plainly instead of staying silent, so it's obvious this
  // answer came from the model's own knowledge, not your uploads.
  if (!retrieval.filename) {
    const reason =
      retrieval.mode === 'below_threshold'
        ? 'no close match found in your documents'
        : 'answered without checking your documents'
    return (
      <div className="retrieval-block">
        <span className="retrieval-badge general-knowledge">
          <span className="retrieval-dot general-knowledge-dot" />
          general knowledge · {reason}
        </span>
      </div>
    )
  }

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
            const relevance = Math.max(0, Math.min(1, c.best_score))
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

function Message({ role, content, error, sources, retrieval }) {
  // Hook must run every render regardless of which branch returns below,
  // so it's declared before the early user-message return.
  const [showEvidence, setShowEvidence] = useState(false)

  if (role === 'user') {
    return (
      <div className="message-row user">
        <div className="bubble user-bubble">{content}</div>
      </div>
    )
  }

  const hasEvidence = Array.isArray(sources) && sources.length > 0

  return (
    <div className="message-row assistant">
      <div className={`bubble assistant-bubble ${error ? 'error-bubble' : ''}`}>
        {error ? (
          <p className="answer-text">{content}</p>
        ) : (
          <div className="answer-text markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}

        {!error && <RetrievalBadge retrieval={retrieval} />}

        {!error && hasEvidence && (
          <>
            <button className="evidence-toggle" onClick={() => setShowEvidence((s) => !s)}>
              {showEvidence ? 'Hide sources' : `Show ${sources.length} source${sources.length > 1 ? 's' : ''}`}
              <span className={`chevron ${showEvidence ? 'open' : ''}`}>›</span>
            </button>
            {showEvidence && (
              <div className="evidence-list">
                {sources.map((chunk, i) => (
                  <EvidenceCard key={i} chunk={chunk} />
                ))}
              </div>
            )}
          </>
        )}
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
// Auth screen (login + register, toggled)
// ─────────────────────────────────────────────────────────────
function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const data = mode === 'login'
        ? await apiLogin(email.trim(), password)
        : await apiRegister(email.trim(), password, name.trim())
      storeAuth(data.token, data.user)
      // The parent (App) checks data.user.email_verified and routes to
      // the verify-pending screen instead of the chat UI if needed -
      // this component doesn't need to know about that.
      onAuthenticated(data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="boot-screen">
      <form className="auth-card" onSubmit={handleSubmit}>
        <span className="eyebrow">your document assistant</span>
        <h1>Vero</h1>
        <p className="auth-subtitle">
          {mode === 'login' ? 'Log in to your account' : 'Create an account'}
        </p>

        {mode === 'register' && (
          <input
            className="auth-input"
            type="text"
            placeholder="Name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        )}
        <input
          className="auth-input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <div className="password-field">
          <input
            className="auth-input"
            type={showPassword ? 'text' : 'password'}
            placeholder={mode === 'register' ? 'Password (min. 8 characters)' : 'Password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={mode === 'register' ? 8 : undefined}
            required
          />
          <button
            type="button"
            className="password-toggle"
            onClick={() => setShowPassword((s) => !s)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            title={showPassword ? 'Hide password' : 'Show password'}
            tabIndex={-1}
          >
            {showPassword ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>

        {error && <p className="auth-error">{error}</p>}

        <button className="auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Sign up'}
        </button>

        <button
          type="button"
          className="auth-toggle"
          onClick={() => { setMode((m) => (m === 'login' ? 'register' : 'login')); setError(null) }}
        >
          {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Log in'}
        </button>
      </form>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// VerifyPendingScreen - shown after login/register instead of the
// chat UI whenever user.email_verified is false. Blocks entry until
// the person either clicks the emailed link (handled by App, which
// re-renders this away once verified) or hits "I've verified" to
// re-check.
// ─────────────────────────────────────────────────────────────
function VerifyPendingScreen({ user, onVerified, onLogout }) {
  const [resendState, setResendState] = useState('idle') // 'idle' | 'sending' | 'sent' | 'error'
  const [checkState, setCheckState] = useState('idle')   // 'idle' | 'checking' | 'not_yet' | 'error'

  async function handleResend() {
    setResendState('sending')
    try {
      await apiResendVerification()
      setResendState('sent')
    } catch {
      setResendState('error')
    }
  }

  async function handleCheckAgain() {
    setCheckState('checking')
    try {
      const freshUser = await apiMe()
      if (freshUser.email_verified) {
        storeAuth(getToken(), freshUser)
        onVerified(freshUser)
      } else {
        setCheckState('not_yet')
      }
    } catch {
      setCheckState('error')
    }
  }

  return (
    <div className="boot-screen">
      <div className="auth-card">
        <span className="eyebrow">your document assistant</span>
        <h1>Vero</h1>
        <p className="auth-subtitle">Verify your email to continue</p>
        <p className="verify-pending-text">
          We sent a verification link to <strong>{user.email}</strong>. Open it, then come back
          here and hit "I've verified".
        </p>
        <p className="verify-pending-hint">
          Didn't get it? If SMTP isn't configured on the backend yet, check the backend's
          terminal output instead - the link gets printed there in dev mode.
        </p>

        <button className="auth-submit" type="button" onClick={handleCheckAgain} disabled={checkState === 'checking'}>
          {checkState === 'checking' ? 'Checking…' : "I've verified, continue"}
        </button>
        {checkState === 'not_yet' && <p className="auth-error">Still not verified - try opening the link first.</p>}
        {checkState === 'error' && <p className="auth-error">Couldn't check right now. Try again in a moment.</p>}

        <button type="button" className="auth-toggle" onClick={handleResend} disabled={resendState === 'sending'}>
          {resendState === 'sending' ? 'Sending…' : resendState === 'sent' ? 'Sent - resend again?' : 'Resend verification email'}
        </button>
        {resendState === 'error' && <p className="auth-error">Could not resend. Try again shortly.</p>}

        <button type="button" className="auth-toggle" onClick={onLogout}>
          Log out
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// ChatApp - everything that used to be App(), now gated behind auth
// ─────────────────────────────────────────────────────────────
function ChatApp({ user, onLogout }) {
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
  const [strictMode, setStrictMode] = useState(false) // "Docs only" - see sendQuestion
  const [uploadNotice, setUploadNotice] = useState(null) // { type: 'ok'|'err', text }
  const scrollRef = useRef(null)
  const isDraggingRef = useRef(false)
  const attachInputRef = useRef(null)
  const chatInputRef = useRef(null)

  const activeSession = sessions.find((s) => s.id === activeId) ?? null
  const loading = loadingSessionId === activeId
  const messagesLoading = messagesLoadingId === activeId

  // The text input is `disabled` while `loading` is true (so people can't
  // send a second question mid-request) - but a disabled input can't hold
  // focus, so the browser blurs it the instant a question is sent. Nothing
  // was refocusing it once the answer came back and it re-enabled, so the
  // cursor just vanished until you clicked the box again. Re-focus it every
  // time loading finishes.
  useEffect(() => {
    if (!loading) {
      chatInputRef.current?.focus()
    }
  }, [loading])

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
      const res = await authFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: targetId, strict_mode: strictMode })
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
          <div className="header-spacer" />
          {user && <span className="user-email" title={user.email}>{user.name || user.email}</span>}
          <button className="logout-btn" onClick={onLogout} title="Log out">
            Log out
          </button>
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
              <button
                type="button"
                className={`strict-toggle ${strictMode ? 'active' : ''}`}
                onClick={() => setStrictMode((s) => !s)}
                aria-pressed={strictMode}
                title={
                  strictMode
                    ? 'Docs only is ON - Vero will only answer from your uploaded documents'
                    : 'Docs only is OFF - Vero answers normally and has no access to your uploaded documents'
                }
              >
                <span className="strict-toggle-dot" />
                Docs only
              </button>
              <input
                ref={chatInputRef}
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

// ─────────────────────────────────────────────────────────────
// App - top-level auth gate. Renders the login/register screen
// until a token exists, then hands off to ChatApp.
// ─────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(() => (getToken() ? getStoredUser() : null))
  const [verifyNotice, setVerifyNotice] = useState(null) // { type: 'ok'|'err', text }

  // authFetch fires this from anywhere (sessions, chat, upload, ...)
  // whenever the server says the token is invalid/expired, so a
  // single listener here is enough to bounce back to the login screen.
  useEffect(() => {
    function handleExpired() { setUser(null) }
    window.addEventListener('auth:expired', handleExpired)
    return () => window.removeEventListener('auth:expired', handleExpired)
  }, [])

  // Handles the link from the verification email: /?verify_token=...
  // Runs once on load regardless of login state - the token alone is
  // enough to verify, no auth header needed. If the verified email
  // matches whoever's currently logged in (e.g. same browser), also
  // clear their "please verify" banner without a page reload.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('verify_token')
    if (!token) return

    // Strip it right away so a refresh doesn't try to re-verify a
    // token that's already been consumed.
    params.delete('verify_token')
    const query = params.toString()
    window.history.replaceState({}, '', window.location.pathname + (query ? `?${query}` : ''))

    apiVerifyEmail(token)
      .then((data) => {
        setVerifyNotice({
          type: 'ok',
          text: data.already ? 'This email was already verified.' : 'Email verified! You’re all set.'
        })
        setUser((prev) => {
          if (!prev || prev.email !== data.user.email) return prev
          const updated = { ...prev, email_verified: true }
          storeAuth(getToken(), updated)
          return updated
        })
      })
      .catch((err) => {
        setVerifyNotice({ type: 'err', text: err.message })
      })
      .finally(() => {
        setTimeout(() => setVerifyNotice(null), 6000)
      })
  }, [])

  function handleLogout() {
    clearAuth()
    setUser(null)
  }

  function renderScreen() {
    if (!user) return <AuthScreen onAuthenticated={setUser} />
    if (!user.email_verified) {
      return <VerifyPendingScreen user={user} onVerified={setUser} onLogout={handleLogout} />
    }
    // key={user.id} forces ChatApp to remount on login/logout so its
    // internal state (sessions, activeId, etc.) never leaks between accounts.
    return <ChatApp key={user.id} user={user} onLogout={handleLogout} />
  }

  return (
    <>
      {verifyNotice && (
        <div className={`verify-toast ${verifyNotice.type === 'err' ? 'err' : 'ok'}`}>
          {verifyNotice.text}
        </div>
      )}
      {renderScreen()}
    </>
  )
}