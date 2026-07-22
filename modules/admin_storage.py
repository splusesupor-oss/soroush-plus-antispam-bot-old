import json
from pathlib import Path

FILE = Path("config/admins.json")

_cache = None
_cache_mtime = None

def _file_mtime():
    try:
        return FILE.stat().st_mtime_ns
    except OSError:
        return None

def load_admins():
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

def save_admins(data):
    global _cache, _cache_mtime
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _cache = data
    _cache_mtime = _file_mtime()

def add_admin(group_id, username):
    data = load_admins()

    gid = str(group_id)
    username = username.replace("@", "")

    if gid not in data:
        data[gid] = []

    if username not in data[gid]:
        data[gid].append(username)

    save_admins(data)
    return True

def is_admin(group_id, username):
    data = load_admins()

    if not username:
        return False

    username = username.replace("@", "")

    # مالک اصلی ربات
    if username == "osine1":
        return True

    return username in data.get(str(group_id), [])

def remove_admin(group_id, username):
    data = load_admins()
    gid = str(group_id)
    username = username.replace("@", "")

    if gid in data and username in data[gid]:
        data[gid].remove(username)
        save_admins(data)
        return True

    return False

