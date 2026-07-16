"""
Pydantic models for the FastAPI surface.

Why this file exists (JD line: "structured outputs, JSON response
formats, ... output validation logic"): under Flask, request/response
shapes were implicit — enforced only by hand-written `.get(...)`
calls in app.py and whatever the frontend happened to send. Pydantic
makes those shapes explicit, validated on the way in (bad request ->
automatic 422 with a field-level error, not a 500 three functions
later) and documented on the way out (FastAPI's auto-generated
OpenAPI schema is a live source of truth for these models — visible
at /docs).

Kept separate from main.py the same way auth.py/db.py are: this
module only knows about shapes, nothing about routing.
"""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator


# ── Auth ─────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    email_verified: bool

    class Config:
        extra = "allow"  # db.py rows may carry a couple of extra columns


class TokenResponse(BaseModel):
    token: str
    user: UserOut


# ── Chat ─────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str
    document_id: Optional[str] = None
    strict_mode: bool = False

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        return v


class SourceChunk(BaseModel):
    content: str
    score: float
    rerank_score: Optional[float] = None
    chunk_index: int
    filename: str
    page_number: Optional[int] = None


class RetrievalInfo(BaseModel):
    mode: str
    document_id: Optional[str] = None
    filename: Optional[str] = None
    best_score: Optional[float] = None
    threshold: Optional[float] = None
    strict_blocked: Optional[bool] = None
    # candidate_documents / other debug-only keys are intentionally
    # left out of the strict schema for now — see main.py note in
    # the /api/chat handler for why they're re-attached loosely.


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk] = []
    retrieval: dict  # loosened vs. RetrievalInfo — see main.py note
    session_id: str


# ── Sessions ─────────────────────────────────────────────────
class CreateSessionRequest(BaseModel):
    title: str = "New chat"


class SessionOut(BaseModel):
    id: str
    title: str

    class Config:
        extra = "allow"


# ── Documents ────────────────────────────────────────────────
class DocumentOut(BaseModel):
    document_id: str
    filename: str
    file_type: str
    upload_timestamp: str
    chunk_count: int


class UploadedFileOut(BaseModel):
    document_id: str
    filename: str
    original_filename: str
    file_type: str
    chunks_stored: int


class UploadErrorOut(BaseModel):
    filename: Optional[str] = None
    error: str


class UploadResponse(BaseModel):
    uploaded: list[UploadedFileOut] = []
    errors: list[UploadErrorOut] = []


class DeleteDocumentResponse(BaseModel):
    deleted: bool
    document_id: str


# ── Generic ──────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str
    qdrant_ready: bool
    db_ready: bool