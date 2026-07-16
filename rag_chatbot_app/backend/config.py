"""
Centralized configuration for the RAG chatbot.

Everything that used to be hardcoded inline (model names, chunk sizes,
the Weaviate URL, allowed file types) lives here so later modules
(vectorstore, document loaders, services, routes) all read from one
source of truth instead of duplicating literals.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documents")
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

# ── Qdrant (vector store) ───────────────────────────────────
# QDRANT_URL: self-hosted default (e.g. local Docker) is
# http://localhost:6333. For Qdrant Cloud, use the cluster URL from
# your dashboard (https://xxxxx.cloud.qdrant.io) and set
# QDRANT_API_KEY - self-hosted instances with no auth configured
# don't need an API key.
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = "DocumentChunk"
# all-MiniLM-L6-v2 (the EMBEDDING_MODEL_NAME default above) outputs
# 384-dim vectors. If you change EMBEDDING_MODEL_NAME to a model with
# a different output size, update this to match, and re-ingest your
# documents - Qdrant collections are created with a fixed vector size
# and can't have it changed after the fact.
EMBEDDING_DIMENSIONS = 384

# ── Embedding model ──────────────────────────────────────────
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ── Chat / LLM ───────────────────────────────────────────────
# Switched from the HuggingFace Inference Providers router (Kimi K2)
# to Google AI Studio's Gemini API, since HF's free monthly inference
# credits were exhausted. Gemini exposes an OpenAI-compatible endpoint
# (https://ai.google.dev/gemini-api/docs/openai), so the `openai`
# SDK's `chat.completions.create(...)` call in agent_service.py works
# unchanged - only the client construction in app.py differs.
# Get a free key from https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-flash-latest")

# ── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))

# ── Supported document types ────────────────────────────────
# Used by the upload endpoint to validate incoming files.
# NOTE: legacy .doc (pre-2007 binary Word format) is intentionally
# excluded — there's no reliable pure-Python library for it. Users
# are asked to convert to .docx instead (see document_loaders.py).
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv",
    ".txt", ".pptx", ".md", ".html", ".htm", ".json", ".xml",
}

# ── PostgreSQL (chat history) ───────────────────────────────
# Defaults match docker-compose.yml so it works out of the box.
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_chatbot")
POSTGRES_USER = os.getenv("POSTGRES_USER", "rag_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "rag_password")

# ── Auth (JWT) ───────────────────────────────────────────────
# JWT_SECRET_KEY MUST be overridden via .env in any real deployment -
# the fallback below is only so the app doesn't crash on a fresh
# clone. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24 * 7))  # 7 days

# ── Answering pipeline ───────────────────────────────────────
# "agent" = the single-model tool-calling loop in agent_service.py.
# "crew" = the 3-agent CrewAI pipeline in crew_service.py (Day 3-4
# of the enhancement plan). Kept as a runtime flag rather than
# deleting agent_service's path — lets you A/B latency/cost/quality
# between the two before committing, and gives you a documented
# fallback if the Crew path misbehaves in front of an interviewer.
USE_CREW = os.getenv("USE_CREW", "false").lower() == "true"

# ── Email verification ──────────────────────────────────────
# Where the verification link in the email should point - the
# frontend dev server by default. The frontend reads ?verify_token=
# off this URL on load and calls POST /api/auth/verify-email.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
EMAIL_VERIFICATION_EXPIRY_HOURS = int(os.getenv("EMAIL_VERIFICATION_EXPIRY_HOURS", 24))

# SMTP is optional. If SMTP_HOST isn't set, email_service.py falls
# back to printing the verification link to the backend console -
# handy for local dev with zero email setup. Set these to actually
# send mail (e.g. Gmail: smtp.gmail.com, port 587, an App Password
# as SMTP_PASSWORD - not your real Gmail password).
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@vero.local")