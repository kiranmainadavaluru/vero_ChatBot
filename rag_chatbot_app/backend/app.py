import os
import re
import secrets
import datetime

import psycopg2.errors
from flask import Flask, request, jsonify
from flask_cors import CORS
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient

import config
import vectorstore
import upload_service
import retrieval_service
import agent_service
import db
import auth
import email_service

app = Flask(__name__)
CORS(app)  # allow the React dev server to call this API

embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
hf_client = InferenceClient(api_key=config.HUGGINGFACEHUB_API_TOKEN)
weaviate_client = None  # set up on startup, see bottom of file
db_ready = False  # set True once PostgreSQL schema is confirmed, see bottom of file

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _title_from_question(question):
    trimmed = question.strip()
    return (trimmed[:60] + "…") if len(trimmed) > 60 else trimmed

# NOTE: the old _build_retrieval_query() history-rewrite step and the
# old ask_llm() fixed retrieve-then-generate function have both been
# replaced by agent_service.run_agent(). The model now sees the chat
# history directly and decides for itself whether to call
# search_documents / list_uploaded_documents / answer directly -
# see agent_service.py.


def _send_verification(user):
    """
    Generates + stores a fresh verification token and emails it.
    Wrapped in try/except so a flaky SMTP server can't turn into a
    500 on the register/resend endpoints - the account still gets
    created, the person just needs to hit "resend" once mail is
    reachable again.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=config.EMAIL_VERIFICATION_EXPIRY_HOURS
    )
    db.set_verification_token(user["id"], token, expires_at)
    try:
        email_service.send_verification_email(user["email"], token)
    except Exception as e:
        print(f"⚠️  send_verification_email failed for {user['email']}: {e}")


# ── Auth routes ──────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip() or None

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "A valid email is required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    if db.get_user_by_email(email) is not None:
        return jsonify({"error": "An account with that email already exists."}), 409

    try:
        user = db.create_user(email, auth.hash_password(password), name=name)
    except psycopg2.errors.UniqueViolation:
        # Two registrations for the same email landed at the same time -
        # the pre-check above missed it, the DB's UNIQUE constraint
        # didn't. Same friendly message either way.
        return jsonify({"error": "An account with that email already exists."}), 409
    except Exception as e:
        return jsonify({"error": f"Could not create your account: {e}"}), 500

    _send_verification(user)

    token = auth.issue_token(user["id"], user["email"])
    return jsonify({"token": token, "user": user}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        user = db.get_user_by_email(email)
    except Exception as e:
        return jsonify({"error": f"Could not reach the database: {e}"}), 503

    if user is None or not auth.verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password."}), 401

    token = auth.issue_token(user["id"], user["email"])
    public_user = {k: v for k, v in user.items() if k != "password_hash"}
    return jsonify({"token": token, "user": public_user})


@app.route("/api/auth/me", methods=["GET"])
@auth.require_auth
def me():
    user = db.get_user_by_id(request.user_id)
    if user is None:
        return jsonify({"error": "User no longer exists."}), 404
    return jsonify(user)


@app.route("/api/auth/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Missing verification token."}), 400

    user = db.get_user_by_verification_token(token)
    if user is None:
        return jsonify({"error": "This verification link is invalid. It may have already been used."}), 400

    if user["email_verified"]:
        user.pop("verification_token_expires", None)
        return jsonify({"verified": True, "already": True, "user": user})

    expires_at = user["verification_token_expires"]
    if expires_at is not None and datetime.datetime.now(datetime.timezone.utc) > expires_at:
        return jsonify({"error": "This verification link has expired. Request a new one from the app."}), 400

    db.mark_email_verified(user["id"])
    user["email_verified"] = True
    user.pop("verification_token_expires", None)  # raw datetime, not JSON-safe / not part of the public user shape
    return jsonify({"verified": True, "already": False, "user": user})


@app.route("/api/auth/resend-verification", methods=["POST"])
@auth.require_auth
def resend_verification():
    user = db.get_user_by_id(request.user_id)
    if user is None:
        return jsonify({"error": "User no longer exists."}), 404
    if user["email_verified"]:
        return jsonify({"error": "This email is already verified."}), 400

    _send_verification(user)
    return jsonify({"sent": True})


# ── Routes ───────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "weaviate_ready": weaviate_client is not None,
        "db_ready": db_ready,
    })


@app.route("/api/sessions", methods=["POST"])
@auth.require_auth
def create_session():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "New chat").strip() or "New chat"
    session = db.create_session(request.user_id, title=title)
    return jsonify(session), 201


@app.route("/api/sessions", methods=["GET"])
@auth.require_auth
def get_sessions():
    return jsonify(db.list_sessions(request.user_id))


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
@auth.require_auth
def get_session_messages(session_id):
    session = db.get_session(session_id, request.user_id)
    if session is None:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404
    return jsonify(db.get_messages(session_id))


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
@auth.require_auth
def remove_session(session_id):
    deleted = db.delete_session(session_id, request.user_id)
    if not deleted:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404
    return jsonify({"deleted": True, "id": session_id})


@app.route("/api/documents", methods=["GET"])
@auth.require_auth
def list_documents():
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503
    return jsonify(vectorstore.list_documents(weaviate_client))


@app.route("/api/documents/<document_id>", methods=["DELETE"])
@auth.require_auth
def remove_document(document_id):
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503

    documents = vectorstore.list_documents(weaviate_client)
    match = next((d for d in documents if d["document_id"] == document_id), None)
    if match is None:
        return jsonify({"error": f"No document found with id '{document_id}'."}), 404

    vectorstore.delete_document(weaviate_client, document_id)

    file_path = os.path.join(config.DOCUMENTS_DIR, match["filename"])
    if os.path.exists(file_path):
        os.remove(file_path)

    return jsonify({"deleted": True, "document_id": document_id})


@app.route("/api/upload", methods=["POST"])
@auth.require_auth
def upload():
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files were uploaded."}), 400

    uploaded = []
    errors = []

    for file_storage in files:
        try:
            summary = upload_service.ingest_upload(weaviate_client, embedding_model, file_storage)
            uploaded.append(summary)
        except (upload_service.UnsupportedFileTypeError, ValueError) as e:
            errors.append({"filename": file_storage.filename, "error": str(e)})
        except Exception as e:
            errors.append({"filename": file_storage.filename, "error": f"Unexpected error: {e}"})

    status_code = 200 if uploaded else 400
    return jsonify({"uploaded": uploaded, "errors": errors}), status_code


@app.route("/api/chat", methods=["POST"])
@auth.require_auth
def chat():
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503

    data = request.get_json(force=True)
    question = (data or {}).get("question", "").strip()
    document_id = (data or {}).get("document_id")  # optional: scope to one document
    session_id = (data or {}).get("session_id")
    strict_mode = bool((data or {}).get("strict_mode", False))

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400
    if not session_id:
        return jsonify({"error": "session_id is required. Create one via POST /api/sessions first."}), 400

    session = db.get_session(session_id, request.user_id)
    if session is None:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404

    try:
        db.add_message(session_id, "user", question)
        if session["title"] == "New chat":
            db.rename_session_if_default(session_id, _title_from_question(question))

        answer, sources, retrieval_info = agent_service.run_agent(
            hf_client,
            weaviate_client,
            embedding_model,
            session_id,
            question,
            document_id=document_id,
            strict_mode=strict_mode,
        )

        db.add_message(session_id, "assistant", answer, sources=sources, retrieval=retrieval_info)
        db.touch_session(session_id)

        return jsonify({
            "answer": answer,
            "sources": sources,
            "retrieval": retrieval_info,
            "session_id": session_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    weaviate_client = vectorstore.get_client()
    print("✅ Connected to Weaviate")
    vectorstore.ensure_schema(weaviate_client, reset=False)

    try:
        db.init_db()
        db_ready = True
    except Exception as e:
        print(f"❌ Could not reach PostgreSQL: {e}")
        print("   Check POSTGRES_HOST/PORT/DB/USER/PASSWORD, or run `docker compose up postgres`.")
        raise

    # Optional dev convenience: if PDF_PATH is explicitly set, ingest
    # that one file at startup. Not required for normal use — the
    # primary way to add documents now is POST /api/upload.
    pdf_path = os.getenv("PDF_PATH")
    if pdf_path and os.path.exists(pdf_path):
        print(f"⏳ Ingesting {pdf_path} (PDF_PATH set) ...")
        upload_service.ingest_saved_file(weaviate_client, embedding_model, pdf_path)

    print("\n🚀 API ready at http://localhost:8000")
    app.run(port=8000, debug=False)