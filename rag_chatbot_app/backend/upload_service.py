"""
Upload ingestion pipeline.

Given an uploaded (or already-on-disk) file, this handles the full
path from bytes to searchable vectors: validating the extension,
sanitizing and de-duplicating the filename, extracting text via
document_loaders, chunking, embedding, and inserting into Weaviate.

Kept separate from routes/app.py so the same pipeline could be reused
by something other than Flask later (e.g. a CLI batch-import script)
without pulling in any web-framework code.
"""
import os
import uuid
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

import config
import document_loaders
import chunking
import pii_service
import vectorstore


class UnsupportedFileTypeError(Exception):
    pass


def is_allowed(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in config.ALLOWED_EXTENSIONS


def resolve_unique_path(directory, filename):
    """
    If `filename` already exists in `directory`, append an
    incrementing " (n)" suffix — the same convention most desktop
    file managers use — instead of silently overwriting the existing
    file.

    Returns (full_path, final_filename).
    """
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return os.path.join(directory, candidate), candidate


def ingest_saved_file(client, embedding_model, file_path, original_filename=None):
    """
    Run the full ingestion pipeline on a file that already exists on
    disk. Used both by ingest_upload() (after saving) and optionally
    at startup.
    """
    original_filename = original_filename or os.path.basename(file_path)
    stored_filename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")

    pages = document_loaders.load_document(file_path)
    chunks = chunking.chunk_pages(pages)

    if not chunks:
        raise ValueError(f"No extractable text found in '{original_filename}'.")

    # PII scrubbing runs before embedding, not after - the point is
    # that raw PII never gets turned into a vector or stored in
    # Qdrant in the first place, not that it's hidden after the fact.
    # See pii_service.py for entity selection and score-threshold
    # reasoning. No-ops entirely when config.ENABLE_PII_SCRUBBING is
    # False.
    chunks, redacted_count = pii_service.scrub_chunks(chunks)
    if redacted_count:
        print(f"🔒 PII scrubbed from {redacted_count}/{len(chunks)} chunk(s) in '{original_filename}'")

    chunk_texts = [c["content"] for c in chunks]
    embeddings = embedding_model.encode(chunk_texts, show_progress_bar=False, batch_size=32)

    document_id = str(uuid.uuid4())
    upload_timestamp = datetime.now(timezone.utc).isoformat()

    metadata_list = [
        {
            "document_id": document_id,
            "filename": stored_filename,
            "file_type": ext,
            "upload_timestamp": upload_timestamp,
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    vectorstore.insert_chunks(client, chunk_texts, embeddings, metadata_list)

    return {
        "document_id": document_id,
        "filename": stored_filename,
        "original_filename": original_filename,
        "file_type": ext,
        "chunks_stored": len(chunks),
    }


def ingest_upload(client, embedding_model, file_storage):
    """
    Validate and save a Flask/Werkzeug FileStorage upload, then run
    it through ingest_saved_file().

    Raises UnsupportedFileTypeError or ValueError on failure - the
    route handler catches these per-file so one bad file in a batch
    doesn't abort the rest.
    """
    original_filename = file_storage.filename
    if not original_filename:
        raise ValueError("Uploaded file has no filename.")

    safe_filename = secure_filename(original_filename)
    if not safe_filename:
        raise ValueError(f"'{original_filename}' is not a valid filename.")

    ext = os.path.splitext(safe_filename)[1].lower()
    if ext == ".doc":
        raise UnsupportedFileTypeError(
            f"'{original_filename}' is a legacy .doc file, which isn't "
            "supported. Please convert to .docx and re-upload."
        )

    if not is_allowed(safe_filename):
        raise UnsupportedFileTypeError(
            f"'{original_filename}' has an unsupported file type."
        )

    save_path, stored_filename = resolve_unique_path(config.DOCUMENTS_DIR, safe_filename)
    file_storage.save(save_path)

    return ingest_saved_file(client, embedding_model, save_path, original_filename=original_filename)