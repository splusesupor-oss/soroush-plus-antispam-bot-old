import json
import os
import time
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / 'config' / 'user_activity.json'
# 🗄️ آرشیو سرد: رکوردهای هرس‌شده اینجا منتقل می‌شوند و هرگز در مسیر داغ
# خوانده نمی‌شوند؛ داده‌ای از بین نمی‌رود.
ARCHIVE_FILE = FILE.parent / 'archive' / 'user_activity_archive.json'
# رکوردهای «فقط timestamp» (بدون هیچ گیف/ویدیو) که این‌قدر روز از آخرین
# فعالیتشان گذشته باشد، آرشیو می‌شوند تا فایل بی‌نهایت رشد نکند.
PRUNE_AFTER_DAYS = 60
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


def _prune(data, now=None):
    """رکوردهای صفرِ قدیمی را به آرشیو منتقل می‌کند.

    فقط کاربرانی هرس می‌شوند که هم gifs و هم videos صفر است و آخرین
    فعالیتشان قدیمی‌تر از ``PRUNE_AFTER_DAYS`` روز است. کاربرانی که
    شمارندهٔ واقعی دارند برای گزارش «فعالیت» نگه داشته می‌شوند.
    """
    now = time.time() if now is None else now
    cutoff = now - PRUNE_AFTER_DAYS * 86400
    removed = {}
    for gid in list(data.keys()):
        users = data[gid]
        for uid in list(users.keys()):
            info = users[uid]
            try:
                inactive = float(info.get('last', 0) or 0) < cutoff
                zero = (
                    int(info.get('gifs', 0) or 0) == 0
                    and int(info.get('videos', 0) or 0) == 0
                )
            except (TypeError, ValueError):
                continue
            if zero and inactive:
                removed.setdefault(gid, {})[uid] = users.pop(uid)
        if not users:
            data.pop(gid)
    if not removed:
        return 0
    count = sum(len(users) for users in removed.values())
    # آرشیو best-effort است؛ خطای آن هرگز نباید flush را بشکند.
    try:
        ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if ARCHIVE_FILE.exists():
            try:
                archive = json.loads(ARCHIVE_FILE.read_text(encoding='utf8'))
            except Exception:
                archive = {}
        else:
            archive = {}
        for gid, users in removed.items():
            archive.setdefault(gid, {}).update(users)
        ARCHIVE_FILE.write_text(
            json.dumps(archive, ensure_ascii=False, separators=(",", ":")),
            encoding='utf8',
        )
    except Exception:
        pass
    return count


def flush():
    """نوشتن batch شده؛ در loop دوره‌ای core فراخوانی می‌شود.

    این فایل روی نصب‌های پرکاربر به چند مگابایت می‌رسد. serialize کردن
    یک‌جای آن قفل GIL را چند صد میلی‌ثانیه نگه می‌داشت و حلقهٔ رویداد را
    متوقف می‌کرد (PERIODIC FLUSH SLOW). حالا:
      1) رکوردهای صفرِ قدیمی به آرشیو منتقل می‌شوند (کنترل حجم)،
      2) خروجی به‌صورت تکه‌تکه (گروه‌به‌گروه) نوشته می‌شود تا GIL بین
         تکه‌ها آزاد شود و حلقهٔ رویداد نفس بکشد،
      3) نوشتن اتمیک است (temp + replace) تا فایل هرگز خراب نشود.
    """
    global _DIRTY
    if not _DIRTY:
        return False
    data = _load()
    _prune(data)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = FILE.with_name(FILE.name + '.tmp')
    with temp_path.open('w', encoding='utf8') as stream:
        stream.write('{')
        first = True
        for gid, users in data.items():
            piece = (
                json.dumps(str(gid), ensure_ascii=False)
                + ':'
                + json.dumps(users, ensure_ascii=False, separators=(",", ":"))
            )
            stream.write(piece if first else ',' + piece)
            first = False
        stream.write('}')
    os.replace(temp_path, FILE)
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
