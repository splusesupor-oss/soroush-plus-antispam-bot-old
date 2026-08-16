import json
import re
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


# Letter/digit class used as a word boundary. ZWNJ is normalized to a space
# first, so it is a separator, not a letter. Do not use \\b — it fails on
# Persian letters.
# Letters/digits only. Arabic comma/question mark must stay separators.
_WORD_CHAR = r"0-9A-Za-zء-یگ"
_PATTERN_CACHE = {}
_PATTERN_CACHE_MAX = 2000


def normalize_filter_text(value):
    """Same Persian folding as command/banned-word paths: ي/ك, ZWNJ, case."""
    if not value:
        return ""
    text = str(value).replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    text = text.replace("ي", "ی").replace("ك", "ک").lower()
    return " ".join(text.split())


def _pattern_for(word):
    key = normalize_filter_text(word)
    if not key:
        return None
    cached = _PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    parts = [re.escape(part) for part in key.split()]
    body = r"\s+".join(parts)
    pattern = re.compile(rf"(?<![{_WORD_CHAR}]){body}(?![{_WORD_CHAR}])")
    if len(_PATTERN_CACHE) >= _PATTERN_CACHE_MAX:
        _PATTERN_CACHE.pop(next(iter(_PATTERN_CACHE)))
    _PATTERN_CACHE[key] = pattern
    return pattern


def find_matching_filter_word(text, words):
    """Return the first stored filter word that appears as a standalone token."""
    haystack = normalize_filter_text(text)
    if not haystack:
        return None
    for word in words or ():
        if not word:
            continue
        pattern = _pattern_for(word)
        if pattern is not None and pattern.search(haystack):
            return word
    return None
