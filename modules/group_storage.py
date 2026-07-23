import json
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / "config" / "groups.json"

_cache = None
_cache_mtime = None


def _group_key(data, group_id):
    """کلید موجود را بدون ساختن رکورد تکراری پیدا می‌کند."""
    raw_key = str(group_id)
    canonical_key = normalize_group_id(group_id)
    if raw_key in data:
        return raw_key
    if canonical_key in data:
        return canonical_key
    return canonical_key


def _file_mtime():
    try:
        return FILE.stat().st_mtime_ns
    except OSError:
        return None

def load_groups():
    global _cache, _cache_mtime
    mtime = _file_mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache

    if mtime is None:
        _cache = {}
    else:
        try:
            _cache = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}

    _cache_mtime = mtime
    return _cache

def save_groups(data):
    global _cache, _cache_mtime
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _cache = data
    _cache_mtime = _file_mtime()

def activate_group(group_id, title):
    data = load_groups()
    key = _group_key(data, group_id)
    group = data.get(key, {})

    group.update({
        "title": title,
        "active": True
    })
    data[key] = group

    save_groups(data)


def deactivate_group(group_id, title):
    data = load_groups()
    key = _group_key(data, group_id)
    group = data.get(key, {})

    group.update({
        "title": title,
        "active": False
    })
    data[key] = group

    save_groups(data)


def set_group_owner(group_id, owner_id):
    data = load_groups()
    key = _group_key(data, group_id)
    group = data.get(key, {})
    group["owner_id"] = int(owner_id)
    data[key] = group
    save_groups(data)


def get_group_owner(group_id):
    data = load_groups()
    return data.get(_group_key(data, group_id), {}).get("owner_id")


def remove_group_owner(group_id):
    data = load_groups()
    key = _group_key(data, group_id)
    group = data.get(key)
    if not group or "owner_id" not in group:
        return False

    del group["owner_id"]
    save_groups(data)
    return True


def is_active(group_id):
    data = load_groups()
    return data.get(_group_key(data, group_id), {}).get("active", False)
