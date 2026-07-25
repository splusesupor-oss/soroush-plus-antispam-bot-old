"""Persistent points for group games."""
import json
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "config" / "game_points.json"


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except Exception:
        return {}


def _save(data):
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add(chat_id, user_id, name, points):
    data = _load()
    group = data.setdefault(str(chat_id), {})
    user = group.setdefault(str(user_id), {"name": name or "Unknown User", "points": 0})
    user["name"] = name or user.get("name", "Unknown User")
    user["points"] += points
    _save(data)
    return user["points"]
