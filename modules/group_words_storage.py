import json
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path("config/group_words.json")

_cache = None
_cache_mtime = None

def _file_mtime():
    try:
        return FILE.stat().st_mtime_ns
    except OSError:
        return None


def load_words():
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


def save_words(data):
    global _cache, _cache_mtime
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _cache = data
    _cache_mtime = _file_mtime()


def add_word(group_id, word):
    data = load_words()
    gid = normalize_group_id(group_id)

    if gid not in data:
        data[gid] = []

    word = word.strip()

    if word and word not in data[gid]:
        data[gid].append(word)
        save_words(data)
        return True

    return False


def remove_word(group_id, word):
    data = load_words()
    gid = normalize_group_id(group_id)

    if gid in data and word in data[gid]:
        data[gid].remove(word)
        save_words(data)
        return True

    return False


def get_words(group_id):
    data = load_words()
    return data.get(normalize_group_id(group_id), [])
