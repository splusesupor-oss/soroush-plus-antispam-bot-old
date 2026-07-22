"""ذخیره‌سازی مستقل اصل/لقب شخصی کاربران."""
import json
from pathlib import Path


FILE = Path("config/user_originals.json")
_pending_users = set()


def load_originals():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_originals(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def begin_registration(user_id):
    _pending_users.add(str(user_id))


def is_waiting_for_original(user_id):
    return str(user_id) in _pending_users


def save_original(user_id, original):
    data = load_originals()
    data[str(user_id)] = original.strip()
    save_originals(data)
    _pending_users.discard(str(user_id))


def get_original(user_id):
    return load_originals().get(str(user_id))
