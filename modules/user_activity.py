import json
import time
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / 'config' / 'user_activity.json'
_CACHE = None
_DIRTY = False


def _load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not FILE.exists():
        _CACHE = {}
    else:
        try:
            _CACHE = json.loads(FILE.read_text(encoding='utf8'))
        except Exception:
            _CACHE = {}
    return _CACHE


def _save(data):
    global _CACHE, _DIRTY
    _CACHE = data
    _DIRTY = True


def flush():
    """نوشتن batch شده؛ در loop دوره‌ای core فراخوانی می‌شود."""
    global _DIRTY
    if not _DIRTY:
        return False
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(_load(), ensure_ascii=False, indent=2), encoding='utf8')
    _DIRTY = False
    return True


def record(chat_id, user_id, message):
    data = _load()
    group = data.setdefault(normalize_group_id(chat_id), {})
    user = group.setdefault(str(user_id), {
        'gifs': 0, 'videos': 0, 'first': time.time(), 'last': time.time(),
    })
    now = time.time()
    user['last'] = now
    user.setdefault('first', now)
    doc = getattr(message, 'document', None) or getattr(
        getattr(message, 'media', None), 'document', None
    )
    mime = (getattr(doc, 'mime_type', None) or '').lower()
    if bool(getattr(message, 'gif', False)) or getattr(message, 'animation', None) or mime == 'image/gif':
        user['gifs'] += 1
    elif mime.startswith('video/'):
        user['videos'] += 1
    _save(data)


def get(chat_id, user_id):
    return _load().get(normalize_group_id(chat_id), {}).get(
        str(user_id), {'gifs': 0, 'videos': 0, 'first': 0, 'last': 0}
    )
