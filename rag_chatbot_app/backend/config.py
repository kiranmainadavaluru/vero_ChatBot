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

# ── Weaviate ─────────────────────────────────────────────────
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS_NAME = "DocumentChunk"

# ── Embedding model ──────────────────────────────────────────
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ── Chat / LLM ───────────────────────────────────────────────
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
CHAT_MODEL = os.getenv("CHAT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")

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