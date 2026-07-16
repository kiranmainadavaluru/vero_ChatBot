"""
FastAPI port of app.py.

Scope of this first pass (Day 1-2 of the enhancement plan): health,
auth, sessions, and /api/chat — the endpoints that matter for the
CrewAI work landing next, plus enough auth surface to prove the
migration pattern generalizes to the rest (upload/documents follow
the identical shape and can be ported mechanically).

Deliberately reuses db.py, auth.py's hashing/token functions,
agent_service.py, and vectorstore.py completely unchanged — none of
that logic is Flask-specific. Only two things are new:
  1. `get_current_user`, a FastAPI dependency replacing the
     `@auth.require_auth` decorator (same JWT verification, just
     wired into FastAPI's DI system instead of a wraps()-based
     decorator).
  2. schemas.py, the Pydantic models replacing hand-parsed
     `request.get_json()` dicts.

Run with: uvicorn main:app --reload --port 8000
(app.py / gunicorn app:app keeps working unchanged during the
migration — both can run side by side on different ports until the
frontend and Dockerfile are switched over.)
"""
import datetime
import os
import re
import secrets

import jwt
import psycopg2.errors
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from werkzeug.utils import secure_filename

import config
import vectorstore
import agent_service
import crew_service
import upload_service
import prompt_guard
import db
import auth
import email_service
from schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserOut,
    ChatRequest, ChatResponse,
    CreateSessionRequest, SessionOut,
    DocumentOut, UploadResponse, UploadedFileOut, UploadErrorOut, DeleteDocumentResponse,
    HealthResponse,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="Vero Chatbot API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to config.FRONTEND_URL before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
llm_client = OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL)
qdrant_client = vectorstore.get_client()
db_ready = False


@app.on_event("startup")
def startup():
    global db_ready
    print("✅ Connected to Qdrant")
    vectorstore.ensure_schema(qdrant_client, reset=False)
    try:
        db.init_db()
        db_ready = True
    except Exception as e:
        print(f"❌ Could not reach PostgreSQL: {e}")
        raise
    print("🚀 FastAPI backend ready at http://localhost:8000 (docs at /docs)")


# ── Auth dependency (replaces @auth.require_auth) ──────────────
def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization[len("Bearer "):].strip()
    try:
        payload = auth.decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return {"user_id": payload["sub"], "email": payload.get("email")}


def _title_from_question(question: str) -> str:
    trimmed = question.strip()
    return (trimmed[:60] + "…") if len(trimmed) > 60 else trimmed


def _send_verification(user: dict):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=config.EMAIL_VERIFICATION_EXPIRY_HOURS
    )
    db.set_verification_token(user["id"], token, expires_at)
    try:
        email_service.send_verification_email(user["email"], token)
    except Exception as e:
        print(f"⚠️  send_verification_email failed for {user['email']}: {e}")


# ── Health ───────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", qdrant_ready=qdrant_client is not None, db_ready=db_ready)


# ── Auth routes ──────────────────────────────────────────────
@app.post("/api/auth/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    email = body.email.strip().lower()

    if db.get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    try:
        user = db.create_user(email, auth.hash_password(body.password), name=body.name)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create your account: {e}")

    _send_verification(user)
    token = auth.issue_token(user["id"], user["email"])
    return TokenResponse(token=token, user=UserOut(**user))


@app.post("/api/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    try:
        user = db.get_user_by_email(body.email.strip().lower())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not reach the database: {e}")

    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = auth.issue_token(user["id"], user["email"])
    public_user = {k: v for k, v in user.items() if k != "password_hash"}
    return TokenResponse(token=token, user=UserOut(**public_user))


@app.get("/api/auth/me", response_model=UserOut)
def me(current=Depends(get_current_user)):
    user = db.get_user_by_id(current["user_id"])
    if user is None:
        raise HTTPException(status_code=404, detail="User no longer exists.")
    return UserOut(**user)


# ── Sessions ─────────────────────────────────────────────────
@app.post("/api/sessions", response_model=SessionOut, status_code=201)
def create_session(body: CreateSessionRequest, current=Depends(get_current_user)):
    title = body.title.strip() or "New chat"
    session = db.create_session(current["user_id"], title=title)
    return SessionOut(**session)


@app.get("/api/sessions", response_model=list[SessionOut])
def get_sessions(current=Depends(get_current_user)):
    return [SessionOut(**s) for s in db.list_sessions(current["user_id"])]


@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str, current=Depends(get_current_user)):
    deleted = db.delete_session(session_id, current["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No session found with id '{session_id}'.")
    return {"deleted": True, "id": session_id}


# ── Documents ────────────────────────────────────────────────
def _ingest_upload_file(client, embedding_model, file: UploadFile) -> dict:
    """
    Adapts a FastAPI UploadFile onto the existing ingest_saved_file()
    pipeline. upload_service.ingest_upload() (the Flask version) calls
    file_storage.save(path) directly on a Werkzeug FileStorage -
    UploadFile has no .save(), so this re-does the same three steps
    (validate filename, resolve a non-clobbering path, write bytes)
    and then hands off to the framework-agnostic ingest_saved_file(),
    same as the Flask route does.
    """
    original_filename = file.filename
    if not original_filename:
        raise ValueError("Uploaded file has no filename.")

    safe_filename = secure_filename(original_filename)
    if not safe_filename:
        raise ValueError(f"'{original_filename}' is not a valid filename.")

    ext = os.path.splitext(safe_filename)[1].lower()
    if ext == ".doc":
        raise upload_service.UnsupportedFileTypeError(
            f"'{original_filename}' is a legacy .doc file, which isn't "
            "supported. Please convert to .docx and re-upload."
        )
    if not upload_service.is_allowed(safe_filename):
        raise upload_service.UnsupportedFileTypeError(
            f"'{original_filename}' has an unsupported file type."
        )

    save_path, _ = upload_service.resolve_unique_path(config.DOCUMENTS_DIR, safe_filename)
    with open(save_path, "wb") as out:
        out.write(file.file.read())

    return upload_service.ingest_saved_file(
        client, embedding_model, save_path, original_filename=original_filename
    )


@app.post("/api/upload", response_model=UploadResponse)
def upload(files: list[UploadFile] = File(...), current=Depends(get_current_user)):
    if qdrant_client is None:
        raise HTTPException(status_code=503, detail="Backend is still starting up, try again in a moment.")
    if not files or all(not f.filename for f in files):
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    uploaded, errors = [], []
    for f in files:
        try:
            summary = _ingest_upload_file(qdrant_client, embedding_model, f)
            uploaded.append(UploadedFileOut(**summary))
        except (upload_service.UnsupportedFileTypeError, ValueError) as e:
            errors.append(UploadErrorOut(filename=f.filename, error=str(e)))
        except Exception as e:
            errors.append(UploadErrorOut(filename=f.filename, error=f"Unexpected error: {e}"))

    return UploadResponse(uploaded=uploaded, errors=errors)


@app.get("/api/documents", response_model=list[DocumentOut])
def list_documents(current=Depends(get_current_user)):
    if qdrant_client is None:
        raise HTTPException(status_code=503, detail="Backend is still starting up, try again in a moment.")
    return [DocumentOut(**d) for d in vectorstore.list_documents(qdrant_client)]


@app.delete("/api/documents/{document_id}", response_model=DeleteDocumentResponse)
def remove_document(document_id: str, current=Depends(get_current_user)):
    if qdrant_client is None:
        raise HTTPException(status_code=503, detail="Backend is still starting up, try again in a moment.")

    documents = vectorstore.list_documents(qdrant_client)
    match = next((d for d in documents if d["document_id"] == document_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"No document found with id '{document_id}'.")

    vectorstore.delete_document(qdrant_client, document_id)

    file_path = os.path.join(config.DOCUMENTS_DIR, match["filename"])
    if os.path.exists(file_path):
        os.remove(file_path)

    return DeleteDocumentResponse(deleted=True, document_id=document_id)


# ── Sessions: message history (the one Day-1 gap) ──────────────
@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str, current=Depends(get_current_user)):
    session = db.get_session(session_id, current["user_id"])
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session found with id '{session_id}'.")
    return db.get_messages(session_id)


# ── Chat (the endpoint the CrewAI Crew plugs into next) ─────
@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, current=Depends(get_current_user)):
    if qdrant_client is None:
        raise HTTPException(status_code=503, detail="Backend is still starting up, try again in a moment.")

    session = db.get_session(body.session_id, current["user_id"])
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session found with id '{body.session_id}'.")

    try:
        db.add_message(body.session_id, "user", body.question)
        if session["title"] == "New chat":
            db.rename_session_if_default(body.session_id, _title_from_question(body.question))

        # Prompt-injection pattern check (Day 6) — a code-level
        # short-circuit before the question ever reaches the LLM, same
        # reasoning as the strict_mode short-circuit below: a pattern
        # match here is a guarantee, not a hope that the model notices
        # and declines on its own. See prompt_guard.py for what this
        # does and doesn't catch (it's a first line of defense, not a
        # complete one).
        if config.ENABLE_PROMPT_INJECTION_GUARD:
            guard_result = prompt_guard.check_prompt_injection(body.question)
            if guard_result["flagged"]:
                answer = (
                    "I can't act on instructions embedded in a message that try to "
                    "override how I'm configured to behave. Feel free to rephrase your "
                    "question about the uploaded documents."
                )
                retrieval_info = {
                    "mode": "blocked",
                    "injection_blocked": True,
                    "matched_patterns": guard_result["matched_patterns"],
                }
                db.add_message(body.session_id, "assistant", answer, sources=[], retrieval=retrieval_info)
                db.touch_session(body.session_id)
                return ChatResponse(answer=answer, sources=[], retrieval=retrieval_info, session_id=body.session_id)

        # NOTE: this is the seam mentioned on Day 1 — config.USE_CREW
        # switches between the single-model tool-calling loop
        # (agent_service.run_agent) and the 3-agent CrewAI pipeline
        # (crew_service.run_crew). Both return the identical
        # (answer, sources, retrieval_info) shape, so this route
        # doesn't change regardless of which is active. Signatures
        # differ slightly — run_crew builds its own LLM internally
        # (see crew_service._build_llm) rather than taking one in,
        # since each CrewAI Agent needs its own LLM handle.
        if config.USE_CREW:
            answer, sources, retrieval_info = crew_service.run_crew(
                qdrant_client,
                embedding_model,
                body.session_id,
                body.question,
                document_id=body.document_id,
                strict_mode=body.strict_mode,
            )
        else:
            answer, sources, retrieval_info = agent_service.run_agent(
                llm_client,
                qdrant_client,
                embedding_model,
                body.session_id,
                body.question,
                document_id=body.document_id,
                strict_mode=body.strict_mode,
            )

        db.add_message(body.session_id, "assistant", answer, sources=sources, retrieval=retrieval_info)
        db.touch_session(body.session_id)

        return ChatResponse(
            answer=answer,
            sources=sources,
            retrieval=retrieval_info,  # dict, not the strict RetrievalInfo model —
                                        # see schemas.py note: candidate_documents'
                                        # shape varies by retrieval mode, so it isn't
                                        # forced into a fixed schema yet
            session_id=body.session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)