"""
PostgreSQL persistence for users, chat sessions and messages.

Kept separate from app.py the same way vectorstore.py is for
Weaviate - this module only knows about rows and SQL, nothing about
Flask or HTTP.

Schema:
  users           - one row per registered account (id, email,
                    password_hash, name, timestamps)
  chat_sessions   - one row per conversation (id, user_id, title,
                    timestamps). Scoped to the owning user via
                    user_id, so list_sessions() only ever returns
                    that user's own chats.
  chat_messages   - one row per question OR answer, linked to a
                    session. Assistant messages also store their
                    `sources` and `retrieval` info as JSONB, so
                    reloading a conversation can show the exact same
                    evidence/routing badges it showed originally,
                    not just the bare text.
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
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    name TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            # Added after the initial users table - IF NOT EXISTS keeps
            # this safe to run against a database created before email
            # verification existed.
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS verification_token TEXT;
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMPTZ;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New chat',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            # Nullable on purpose: keeps this migration safe to run
            # against a database that already has sessions from
            # before auth existed. New sessions always get a user_id
            # from app.py (see require_auth), old ones just won't
            # show up for anyone until manually backfilled.
            cur.execute("""
                ALTER TABLE chat_sessions
                ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
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
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
                ON chat_sessions (user_id);
            """)
    print("✅ PostgreSQL schema ready (users, chat_sessions, chat_messages)")


# ── Users ────────────────────────────────────────────────────
def create_user(email, password_hash, name=None):
    user_id = uuid.uuid4()
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, email, password_hash, name) VALUES (%s, %s, %s, %s) "
                "RETURNING id, email, name, created_at, email_verified",
                (str(user_id), email.lower().strip(), password_hash, name),
            )
            row = cur.fetchone()
    return _user_row_to_dict(row)


def get_user_by_email(email):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, name, created_at, email_verified "
                "FROM users WHERE email = %s",
                (email.lower().strip(),),
            )
            row = cur.fetchone()
    if row is None:
        return None
    user = _user_row_to_dict((row[0], row[1], row[3], row[4], row[5]))
    user["password_hash"] = row[2]
    return user


def get_user_by_id(user_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, created_at, email_verified FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return _user_row_to_dict(row) if row else None


def set_verification_token(user_id, token, expires_at):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET verification_token = %s, verification_token_expires = %s "
                "WHERE id = %s",
                (token, expires_at, user_id),
            )


def get_user_by_verification_token(token):
    """
    Returns the user dict plus verification_token_expires if the token
    matches a pending (unconsumed) verification, else None. Doesn't
    filter on expiry here - app.py checks that so it can return a
    specific "link expired" message vs. "invalid token".
    """
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, created_at, email_verified, verification_token_expires "
                "FROM users WHERE verification_token = %s",
                (token,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    user = _user_row_to_dict(row[:5])
    user["verification_token_expires"] = row[5]
    return user


def mark_email_verified(user_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET email_verified = TRUE, verification_token = NULL, "
                "verification_token_expires = NULL WHERE id = %s",
                (user_id,),
            )


# ── Sessions ─────────────────────────────────────────────────
def create_session(user_id, title="New chat"):
    session_id = uuid.uuid4()
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (id, user_id, title) VALUES (%s, %s, %s) "
                "RETURNING id, title, created_at, updated_at",
                (str(session_id), user_id, title),
            )
            row = cur.fetchone()
    return _session_row_to_dict(row)


def list_sessions(user_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions "
                "WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    return [_session_row_to_dict(r) for r in rows]


def get_session(session_id, user_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions "
                "WHERE id = %s AND user_id = %s",
                (session_id, user_id),
            )
            row = cur.fetchone()
    return _session_row_to_dict(row) if row else None


def delete_session(session_id, user_id):
    with _Connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s AND user_id = %s",
                (session_id, user_id),
            )
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


def _user_row_to_dict(row):
    return {
        "id": str(row[0]),
        "email": row[1],
        "name": row[2],
        "created_at": row[3].isoformat(),
        "email_verified": row[4],
    }


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