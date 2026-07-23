import json
import os

from modules.group_id import normalize_group_id

FILE = "config/group_banned_words.json"

_cache = None
_cache_mtime = None

def _file_mtime():
    try:
        return os.stat(FILE).st_mtime_ns
    except OSError:
        return None


def load():
    global _cache, _cache_mtime
    mtime = _file_mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache

    if mtime is None:
        _cache = {}
    else:
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}

    _cache_mtime = mtime
    return _cache


def save(data):
    global _cache, _cache_mtime
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache = data
    _cache_mtime = _file_mtime()


def enable(chat_id):
    data = load()
    data[normalize_group_id(chat_id)] = True
    save(data)


def disable(chat_id):
    data = load()
    data[normalize_group_id(chat_id)] = False
    save(data)


def is_enabled(chat_id):
    data = load()
    return data.get(normalize_group_id(chat_id), True)
