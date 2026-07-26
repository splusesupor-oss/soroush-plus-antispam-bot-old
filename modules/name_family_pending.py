"""Persistent review queue for structurally valid Name & Family answers outside the database."""
import json
import time
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "config" / "name_family_pending.json"


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except Exception:
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record(category, letter, raw_answer, normalized_answer, chat_id, user_id):
    """Store unknown but well-formed answers for later category review, without approval."""
    data = _load()
    key = f"{category}|{letter}|{normalized_answer}"
    now = time.time()
    item = data.get(key)
    if item is None:
        item = {
            "category": category,
            "letter": letter,
            "raw_answer": raw_answer,
            "normalized_answer": normalized_answer,
            "count": 0,
            "first_seen_at": now,
            "last_seen_at": now,
            "chat_ids": [],
            "user_ids": [],
            "status": "pending",
        }
        data[key] = item
    item["count"] = int(item.get("count", 0)) + 1
    item["last_seen_at"] = now
    for field, value in (("chat_ids", str(chat_id)), ("user_ids", str(user_id))):
        values = item.setdefault(field, [])
        if value not in values:
            values.append(value)
    _save(data)
    return item
