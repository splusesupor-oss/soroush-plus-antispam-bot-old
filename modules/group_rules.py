"""Persistent administrator-managed rules for each group."""
import json
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / "config" / "group_rules.json"
_WAITING = set()
MAX_RULES_LENGTH = 4000


def _key(chat_id):
    return normalize_group_id(chat_id)


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def begin(chat_id, user_id):
    _WAITING.add((_key(chat_id), str(user_id)))


def waiting(chat_id, user_id):
    return (_key(chat_id), str(user_id)) in _WAITING


def cancel(chat_id, user_id):
    _WAITING.discard((_key(chat_id), str(user_id)))


def save(chat_id, user_id, text):
    rules = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    if not rules or len(rules) > MAX_RULES_LENGTH:
        return False
    data = _load()
    data[_key(chat_id)] = {"rules": rules, "updated_by": str(user_id)}
    _save(data)
    cancel(chat_id, user_id)
    return True


def get(chat_id):
    return _load().get(_key(chat_id), {}).get("rules")


def remove(chat_id):
    data = _load()
    if _key(chat_id) not in data:
        return False
    del data[_key(chat_id)]
    _save(data)
    return True


def format_rules(chat_id):
    rules = get(chat_id)
    if not rules:
        return None
    lines = rules.splitlines()
    numbered = "\n".join(f"{index}- {line}" for index, line in enumerate(lines, 1))
    return (
        "📜 قوانین گروه:\n\n"
        f"{numbered}\n\n"
        "کاربرانی که قوانین گروه را رعایت نکنند طبق قوانین گروه اخطار دریافت خواهند کرد."
    )
