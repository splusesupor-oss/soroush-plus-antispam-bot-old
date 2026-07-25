"""Persistent last pinned message per Soroush Plus group."""
import json
from pathlib import Path
from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / "config" / "pinned_messages.json"


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except Exception:
        return {}


def save(chat_id, message_id):
    data = _load()
    data[normalize_group_id(chat_id)] = int(message_id)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get(chat_id):
    return _load().get(normalize_group_id(chat_id))
