"""Centralized Soroush Plus global-owner authentication by user ID."""
import json
from pathlib import Path


FILE = Path(__file__).resolve().parent.parent / "config" / "owner.json"
DEFAULT_GLOBAL_OWNER_ID = 68074059


def normalize_username(username):
    if username is None:
        return None
    normalized = str(username).strip().lstrip("@").strip().lower()
    return normalized or None


def get_owner():
    if not FILE.exists():
        return {"user_id": DEFAULT_GLOBAL_OWNER_ID, "username": None}
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return {
            "user_id": int(data.get("user_id", DEFAULT_GLOBAL_OWNER_ID)),
            "username": normalize_username(data.get("username")),
        }
    except Exception:
        return {"user_id": DEFAULT_GLOBAL_OWNER_ID, "username": None}


def is_global_owner(user):
    """Only the configured Soroush Plus user ID is the global owner."""
    if user is None:
        return False
    user_id = getattr(user, "id", user)
    try:
        return int(user_id) == get_owner()["user_id"]
    except (TypeError, ValueError):
        return False


is_owner = is_global_owner
