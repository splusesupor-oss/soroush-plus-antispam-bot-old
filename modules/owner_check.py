"""Centralized Soroush Plus global-owner username authentication."""
import json
from pathlib import Path


FILE = Path(__file__).resolve().parent.parent / "config" / "owner.json"


def normalize_username(username):
    if username is None:
        return None
    normalized = str(username).strip().lstrip("@").strip().lower()
    return normalized or None


def get_owner():
    if not FILE.exists():
        return None
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return normalize_username(data.get("username"))
    except Exception:
        return None


def is_global_owner(username):
    owner = get_owner()
    return owner is not None and normalize_username(username) == owner


# Backward-compatible public alias for existing imports.
is_owner = is_global_owner
