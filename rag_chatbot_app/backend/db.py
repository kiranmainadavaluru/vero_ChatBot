"""
PostgreSQL persistence for chat sessions and messages.

Kept separate from app.py the same way vectorstore.py is for
Weaviate - this module only knows about rows and SQL, nothing about
Flask or HTTP.

Schema:
  chat_sessions   - one row per conversation (id, title, timestamps)
  chat_messages   - one row per question OR answer, linked to a
                    session. Assistant messages also store their
                    `sources` and `retrieval` info as JSONB, so
                    reloading a conversation can show the exact same
                    evidence/routing badges it showed originally,
                    not just the bare text.

No user table yet - there's no auth system in this project, so a
user_id column would be dead weight right now. When auth exists,
add `user_id UUID REFERENCES users(id)` to chat_sessions and filter
list_sessions() by it.
"""
import uuid

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

import config

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            1, 10,
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            dbname=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
        )
    return _pool


class _Connection:
    """
    Borrow a connection from the pool, commit on success, roll back
    on any exception, always return it to the pool. Used as:

        with _Connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    def __enter__(self):
        self.conn = get_pool().getconn()
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        get_pool().putconn(self.conn)
        return False


def init_db():
    """Create tables/indexes if they don't exist yet. Safe to call every startup."""
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New chat',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sources JSONB,
                    retrieval JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
                ON chat_messages (session_id);
            """)
    print("✅ PostgreSQL schema ready (chat_sessions, chat_messages)")


# ── Sessions ─────────────────────────────────────────────────
def create_session(title="New chat"):
    session_id = uuid.uuid4()
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (id, title) VALUES (%s, %s) "
                "RETURNING id, title, created_at, updated_at",
                (str(session_id), title),
            )
            row = cur.fetchone()
    return _session_row_to_dict(row)


def list_sessions():
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions "
                "ORDER BY updated_at DESC"
            )
            rows = cur.fetchall()
    return [_session_row_to_dict(r) for r in rows]


def get_session(session_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
    return _session_row_to_dict(row) if row else None


def delete_session(session_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            deleted = cur.rowcount > 0
    return deleted


def rename_session_if_default(session_id, new_title):
    """
    Only overwrite the title if it's still the 'New chat' placeholder,
    so this never clobbers a title someone renames later.
    """
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET title = %s, updated_at = now() "
                "WHERE id = %s AND title = 'New chat'",
                (new_title, session_id),
            )


def touch_session(session_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET updated_at = now() WHERE id = %s",
                (session_id,),
            )


# ── Messages ─────────────────────────────────────────────────
def add_message(session_id, role, content, sources=None, retrieval=None):
    message_id = uuid.uuid4()
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, sources, retrieval) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, session_id, role, content, sources, retrieval, created_at",
                (
                    str(message_id), session_id, role, content,
                    psycopg2.extras.Json(sources) if sources is not None else None,
                    psycopg2.extras.Json(retrieval) if retrieval is not None else None,
                ),
            )
            row = cur.fetchone()
    return _message_row_to_dict(row)


def get_messages(session_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, session_id, role, content, sources, retrieval, created_at "
                "FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,),
            )
            rows = cur.fetchall()
    return [_message_row_to_dict(r) for r in rows]


def _session_row_to_dict(row):
    return {
        "id": str(row[0]),
        "title": row[1],
        "created_at": row[2].isoformat(),
        "updated_at": row[3].isoformat(),
    }


def _message_row_to_dict(row):
    return {
        "id": str(row[0]),
        "session_id": str(row[1]),
        "role": row[2],
        "content": row[3],
        "sources": row[4],
        "retrieval": row[5],
        "created_at": row[6].isoformat(),
    }