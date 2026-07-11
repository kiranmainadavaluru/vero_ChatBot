"""
Auth: password hashing + JWT issuing/verification.

Kept separate from app.py the same way db.py/vectorstore.py are -
this module only knows about credentials and tokens, nothing about
Flask routing except the one decorator it exposes for protecting
routes.

Password hashing uses werkzeug's scrypt-based helpers (already a
Flask dependency, no extra install). Tokens are stateless JWTs
signed with JWT_SECRET_KEY - the server doesn't store sessions,
it just verifies the signature + expiry on every request.
"""
import datetime
from functools import wraps

import jwt
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

import config


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def issue_token(user_id, email):
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token):
    """Returns the payload dict, or raises jwt.PyJWTError on bad/expired token."""
    return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])


def _extract_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()


def require_auth(fn):
    """
    Route decorator. On success sets request.user_id / request.user_email
    and calls the route. On failure returns 401 before the route runs.

    Usage:
        @app.route("/api/sessions", methods=["GET"])
        @auth.require_auth
        def get_sessions():
            ...use request.user_id...
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Missing or malformed Authorization header."}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired, please log in again."}), 401
        except jwt.PyJWTError:
            return jsonify({"error": "Invalid token."}), 401

        request.user_id = payload["sub"]
        request.user_email = payload.get("email")
        return fn(*args, **kwargs)
    return wrapper
