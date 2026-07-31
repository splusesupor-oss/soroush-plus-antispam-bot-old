"""🔐 لایهٔ ذخیره‌سازی اتمیک سیستم اقتصاد.

تنها جایی که فایل دیتابیس اقتصاد باز و نوشته می‌شود همین فایل است. هیچ
بازی یا ماژول دیگری نباید مستقیماً به آن دست بزند.

تضمین‌ها:
  • هر تغییر داخل ``transaction()`` انجام می‌شود که یک قفل بازگشتی
    (``RLock``) می‌گیرد، پس دو Thread هم‌زمان نمی‌توانند موجودی را خراب
    کنند.
  • نوشتن روی دیسک اتمیک است (فایل موقت + ``os.replace``)، پس قطع برق
    وسط کار، فایل نیمه‌نوشته باقی نمی‌گذارد.
  • اگر بلوک تراکنش استثنا بدهد، هیچ تغییری ذخیره نمی‌شود (rollback).
  • تراکنش‌های تودرتو فقط در پایان بیرونی‌ترین بلوک روی دیسک می‌نشینند،
    پس یک عملیات مرکب (مثل انتقال) نیمه‌کاره ذخیره نمی‌شود.
"""
import copy
import json
import os
import tempfile
import threading
from pathlib import Path

DATA_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "economy.json"
)

_LOCK = threading.RLock()
_state = threading.local()

_cache = None
_cache_mtime = None
_dirty = False

EMPTY = {"users": {}, "meta": {"version": 1, "sequence": 0}}


def _mtime():
    try:
        return DATA_FILE.stat().st_mtime_ns
    except OSError:
        return None


def _read():
    """خواندن از دیسک با کش مبتنی بر mtime."""
    global _cache, _cache_mtime
    mtime = _mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache
    if mtime is None:
        _cache = copy.deepcopy(EMPTY)
    else:
        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("root is not a dict")
            raw.setdefault("users", {})
            raw.setdefault("meta", {"version": 1, "sequence": 0})
            raw["meta"].setdefault("sequence", 0)
            _cache = raw
        except (OSError, ValueError):
            # فایل خراب نباید ربات را از کار بیندازد.
            _cache = copy.deepcopy(EMPTY)
    _cache_mtime = mtime
    return _cache


def _write(data):
    global _cache, _cache_mtime, _dirty
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=str(DATA_FILE.parent),
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, DATA_FILE)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    _cache = data
    _cache_mtime = _mtime()
    _dirty = False


class _Transaction:
    """مدیر زمینهٔ تراکنش؛ از ``transaction()`` استفاده کنید.

    ``defer=True`` یعنی تغییر فقط در حافظه بماند و نوشتن روی دیسک به
    ``flush()`` سپرده شود. برای شمارنده‌های پرتکرار (مثل شمارش پیام) که
    در هر پیام صدا زده می‌شوند و از دست رفتنشان فاجعه نیست.
    """

    def __init__(self, defer=False):
        self._defer = defer

    def __enter__(self):
        _LOCK.acquire()
        depth = getattr(_state, "depth", 0)
        if depth == 0:
            # کپی عمیق: تا وقتی تراکنش موفق نشده، داده‌های اصلی دست‌نخورده‌اند.
            # در حالت defer از خودِ کش استفاده می‌شود تا هزینهٔ کپی و نوشتن
            # در مسیر داغ پرداخت نشود.
            _state.data = _read() if self._defer else copy.deepcopy(_read())
            _state.deferred = self._defer
        _state.depth = depth + 1
        return _state.data

    def __exit__(self, exc_type, exc, tb):
        global _dirty
        try:
            _state.depth -= 1
            if _state.depth == 0:
                if exc_type is None:
                    if getattr(_state, "deferred", False):
                        # فقط علامت‌گذاری؛ نوشتن در flush انجام می‌شود.
                        _dirty = True
                    else:
                        _write(_state.data)
                _state.data = None
                _state.deferred = False
        finally:
            _LOCK.release()
        return False


def transaction(defer=False):
    """بلوک اتمیک برای خواندن-تغییر-نوشتن.

        with transaction() as data:
            data["users"]["1"]["bronze"] += 5

    با ``defer=True`` نوشتن روی دیسک به ``flush()`` موکول می‌شود.
    """
    return _Transaction(defer)


def flush():
    """تغییرات معوق را روی دیسک می‌نویسد. خروجی True یعنی نوشت."""
    global _dirty
    with _LOCK:
        if not _dirty:
            return False
        if getattr(_state, "depth", 0) > 0:
            # وسط یک تراکنش هستیم؛ خروج آن خودش می‌نویسد.
            return False
        _write(_cache if _cache is not None else copy.deepcopy(EMPTY))
        _dirty = False
        return True


def is_dirty():
    return _dirty


def snapshot():
    """کپی فقط-خواندنی از کل داده‌ها."""
    with _LOCK:
        if getattr(_state, "depth", 0) > 0:
            return copy.deepcopy(_state.data)
        return copy.deepcopy(_read())


def next_sequence(data):
    """شمارندهٔ یکنواخت صعودی برای ترتیب‌گذاری تراکنش‌ها و رتبه‌بندی."""
    meta = data.setdefault("meta", {"version": 1, "sequence": 0})
    meta["sequence"] = int(meta.get("sequence", 0)) + 1
    return meta["sequence"]


def reset_all():
    """پاک‌سازی کامل — فقط برای تست."""
    global _cache, _cache_mtime, _dirty
    with _LOCK:
        _cache = None
        _cache_mtime = None
        _dirty = False
        _state.depth = 0
        _state.data = None
        try:
            DATA_FILE.unlink()
        except OSError:
            pass


def use_file(path):
    """تغییر مسیر فایل — فقط برای تست."""
    global DATA_FILE, _cache, _cache_mtime, _dirty
    with _LOCK:
        DATA_FILE = Path(path)
        _cache = None
        _cache_mtime = None
        _dirty = False
        _state.depth = 0
        _state.data = None
