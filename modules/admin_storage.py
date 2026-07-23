"""ID-based registered group admin storage."""
import json
from pathlib import Path


FILE = Path(__file__).resolve().parent.parent / "config" / "admins.json"


def load_admins():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_admins(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_admin(group_id, user_id, username=None):
    data = load_admins()
    gid = str(group_id)
    entries = data.setdefault(gid, [])
    normalized_id = str(user_id)

    if any(
        isinstance(entry, dict) and str(entry.get("user_id")) == normalized_id
        for entry in entries
    ):
        return False

    entries.append({
        "user_id": normalized_id,
        "username": username or None,
    })
    save_admins(data)
    return True


def is_admin(group_id, user_id):
    if user_id is None:
        return False
    normalized_id = str(user_id)
    for entry in load_admins().get(str(group_id), []):
        if isinstance(entry, dict) and str(entry.get("user_id")) == normalized_id:
            return True
    return False


def remove_admin(group_id, user_id):
    data = load_admins()
    gid = str(group_id)
    if gid not in data:
        return False

    normalized_id = str(user_id)
    original_length = len(data[gid])
    data[gid] = [
        entry for entry in data[gid]
        if not (
            isinstance(entry, dict)
            and str(entry.get("user_id")) == normalized_id
        )
    ]
    if len(data[gid]) == original_length:
        return False

    save_admins(data)
    return True
