import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient

import config
import vectorstore
import upload_service
import retrieval_service
import db

app = Flask(__name__)
CORS(app)  # allow the React dev server to call this API

embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
hf_client = InferenceClient(api_key=config.HUGGINGFACEHUB_API_TOKEN)
weaviate_client = None  # set up on startup, see bottom of file
db_ready = False  # set True once PostgreSQL schema is confirmed, see bottom of file


def _title_from_question(question):
    trimmed = question.strip()
    return (trimmed[:60] + "…") if len(trimmed) > 60 else trimmed


# ── Conversation-aware retrieval query ─────────────────────
MAX_HISTORY_TURNS_FOR_REWRITE = 4  # last N messages fed to the rewriter


def _build_retrieval_query(session_id, current_question):
    """
    Turn short follow-up questions into standalone search queries by
    asking a small LLM call to rewrite them using the recent chat
    history. This makes retrieval focus on the *intent* of the
    current question (e.g. "a number") while still keeping the
    *topic* from earlier turns (e.g. "annual leave").

    If anything fails or there is no history, the original question
    is returned unchanged so retrieval still works.
    """
    try:
        messages = db.get_messages(session_id)
    except Exception:
        return current_question

    prior = [
        m for m in messages
        if not (m["role"] == "user" and m["content"].strip() == current_question.strip())
    ][-MAX_HISTORY_TURNS_FOR_REWRITE:]

    if not prior:
        return current_question

    history_lines = [f"{m['role'].capitalize()}: {m['content']}" for m in prior]
    history_block = "\n".join(history_lines)

    rewrite_prompt = f"""You rewrite the user's latest question into a
single, self-contained search query for a document search engine.
Keep the intent of the latest question exactly, but resolve any
pronouns or missing topic using the recent conversation. Reply
with ONLY the rewritten query on one line, no quotes, no prefix.

Recent conversation:
{history_block}

Latest question: {current_question}

Rewritten search query:"""

    try:
        completion = hf_client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": rewrite_prompt}],
            max_tokens=60,
            temperature=0.0,
        )
        rewritten = completion.choices[0].message.content.strip().splitlines()[0].strip()
        if 3 <= len(rewritten) <= 300:
            return rewritten
    except Exception:
        pass
    return current_question


# ── Answering ────────────────────────────────────────────────
def ask_llm(question, retrieved_chunks):
    """
    If we have relevant chunks, ground the answer in them.
    If we have none, answer from the model's general knowledge and
    tell the user the answer is not from an uploaded document.
    """
    if retrieved_chunks:
        context = "\n\n".join([chunk["content"] for chunk in retrieved_chunks])
        prompt = f"""You are Vero, a helpful assistant.
Answer the question using the context below. Ground your answer
in this context and do not invent facts that are not supported by
it. Keep the answer clear and concise.

Context:
{context}

Question: {question}

Answer:"""
    else:
        prompt = f"""You are Vero, a helpful assistant.
The user has not uploaded any relevant document for this question,
so answer using your general knowledge. Keep the answer clear and
concise, and mention briefly that the answer is not from an
uploaded document.

Question: {question}

Answer:"""

    completion = hf_client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.0,
    )
    return completion.choices[0].message.content.strip()


# ── Routes ───────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "weaviate_ready": weaviate_client is not None,
        "db_ready": db_ready,
    })


@app.route("/api/sessions", methods=["POST"])
def create_session():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "New chat").strip() or "New chat"
    session = db.create_session(title=title)
    return jsonify(session), 201


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    return jsonify(db.list_sessions())


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    session = db.get_session(session_id)
    if session is None:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404
    return jsonify(db.get_messages(session_id))


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def remove_session(session_id):
    deleted = db.delete_session(session_id)
    if not deleted:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404
    return jsonify({"deleted": True, "id": session_id})


@app.route("/api/documents", methods=["GET"])
def list_documents():
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503
    return jsonify(vectorstore.list_documents(weaviate_client))


@app.route("/api/documents/<document_id>", methods=["DELETE"])
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
def chat():
    if weaviate_client is None:
        return jsonify({"error": "Backend is still starting up, try again in a moment."}), 503

    data = request.get_json(force=True)
    question = (data or {}).get("question", "").strip()
    document_id = (data or {}).get("document_id")  # optional: scope to one document
    session_id = (data or {}).get("session_id")

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400
    if not session_id:
        return jsonify({"error": "session_id is required. Create one via POST /api/sessions first."}), 400

    session = db.get_session(session_id)
    if session is None:
        return jsonify({"error": f"No session found with id '{session_id}'."}), 404

    try:
        db.add_message(session_id, "user", question)
        if session["title"] == "New chat":
            db.rename_session_if_default(session_id, _title_from_question(question))

        relevant_chunks, retrieval_info = retrieval_service.retrieve(
            weaviate_client,
            embedding_model,
            _build_retrieval_query(session_id, question),
            top_k=5,
            document_id=document_id,
        )

        # No relevant chunks? Fall back to general knowledge instead of refusing.
        if not relevant_chunks:
            answer_text = ask_llm(question, [])
            db.add_message(session_id, "assistant", answer_text, retrieval=retrieval_info)
            db.touch_session(session_id)
            return jsonify({
                "answer": answer_text,
                "sources": [],
                "retrieval": retrieval_info,
                "session_id": session_id,
            })

        answer = ask_llm(question, relevant_chunks)

        sources = [
            {
                "content": c["content"],
                "distance": round(c["_additional"]["distance"], 4),
                "chunk_index": c["chunk_index"],
                "filename": c["filename"],
                "page_number": c["page_number"],
            }
            for c in relevant_chunks
        ]

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

    print("\n🚀 API ready at http://localhost:5000")
    app.run(port=5000, debug=False)