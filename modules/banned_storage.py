"""ذخیره‌سازی سازگارِ کاربران بن‌شده به‌صورت دائمی برای هر گروه."""
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from modules.group_id import normalize_group_id


FILE = Path(__file__).resolve().parent.parent / "config" / "banned_users.json"

# ✍️ نویسندهٔ تک‌نخی: نوشتن روی دیسک FIFO و خارج از حلقهٔ رویداد انجام
# می‌شود. با یک worker، ترتیب نوشتن‌ها هرگز جابه‌جا نمی‌شود.
_WRITER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="banned-save")

# ⚡️ کش mtime-محور — دقیقاً همان الگوی modules/admin_storage.py.
# فایل banned_users.json ممکن است چند مگابایت باشد؛ خواندن و پارس آن در
# هر پیام، حلقهٔ رویداد را روی حافظهٔ کند گوشی قفل می‌کرد. حالا فایل فقط
# وقتی دوباره خوانده می‌شود که واقعاً تغییر کرده باشد (mtime عوض شود).
# منطق بن هیچ تغییری نکرده است.
_cache = None
_cache_mtime = None
# تا وقتی نوشتنی در صف نخ نویسنده است، کش حافظه مرجع است؛ وگرنه load
# ممکن بود دیسکِ هنوز-عقب‌مانده را «جدیدتر» ببیند و کش تازه را با آن
# جایگزین کند.
_pending_writes = 0


def load_banned():
    global _cache, _cache_mtime
    if _cache is not None and _pending_writes > 0:
        return _cache
    try:
        mtime = FILE.stat().st_mtime_ns
    except OSError:
        mtime = None
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


def _write_payload(payload):
    """نوشتن اتمیک (temp + replace)؛ فقط داخل نخ نویسنده اجرا می‌شود."""
    global _cache_mtime, _pending_writes
    temp_path = None
    try:
        handle, temp_path = tempfile.mkstemp(
            dir=str(FILE.parent), suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        os.replace(temp_path, FILE)
        temp_path = None
        _cache_mtime = FILE.stat().st_mtime_ns
    except Exception:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    finally:
        _pending_writes = max(0, _pending_writes - 1)


def save_banned(data):
    """ذخیرهٔ بن‌ها بدون فریز کردن ربات.

    این فایل به چند مگابایت رسیده است. نوشتنِ همگامِ آن با indent روی
    حافظهٔ کند گوشی، حلقهٔ رویداد را ۵ تا ۸ ثانیه یخ می‌زد (فریز بعد از
    هر بن خودکار؛ همان کندی «ثبت مالک/لغو مالک»). حالا:
      1) کش بلافاصله به‌روز می‌شود؛ همهٔ خواندن‌ها همان لحظه دادهٔ جدید
         را می‌بینند (منطق بن هیچ تغییری نکرده).
      2) serialize فشرده است (بدون indent → تقریباً نصف).
      3) نوشتن روی دیسک به نخ نویسندهٔ تک‌نخی سپرده می‌شود تا FUSE
         کندِ اندروید، حلقهٔ رویداد را بلاک نکند. ترتیب نوشتن‌ها با
         یک worker تضمین‌شده FIFO است.
    """
    global _cache, _pending_writes
    _cache = data
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    _pending_writes += 1
    try:
        _WRITER.submit(_write_payload, payload)
    except Exception:
        # اگر نخ نویسنده در دسترس نبود (مثلاً هنگام خاموش شدن)، همان
        # مسیر همگام قبلی به عنوان آخرین راه استفاده می‌شود.
        _write_payload(payload)


def _normalise_identifier(value):
    if value is None:
        return None
    value = str(value).replace("@", "").strip().lower()
    return value or None


def _entry_matches(
    entry, user_id=None, username=None, display_name=None, extra_identifiers=None
):
    identifiers = {
        value for value in (
            _normalise_identifier(user_id),
            _normalise_identifier(username),
            _normalise_identifier(display_name),
            *(_normalise_identifier(value) for value in (extra_identifiers or [])),
        ) if value
    }

    if isinstance(entry, dict):
        values = [
            entry.get("user_id"),
            entry.get("username"),
            entry.get("display_name"),
            *entry.get("username_aliases", []),
        ]
    else:
        values = [entry]

    return any(
        _normalise_identifier(value) in identifiers
        for value in values
        if value is not None
    )


def add_banned(
    group_id,
    user_id,
    username=None,
    display_name=None,
    reason="",
    source="system",
):
    """کاربر را با شناسه پایدار و اطلاعات نمایشی در ذخیرهٔ موجود ثبت می‌کند."""
    data = load_banned()
    gid = normalize_group_id(group_id)
    entries = data.setdefault(gid, [])
    record = {
        "user_id": str(user_id),
        "username": username or None,
        "display_name": display_name or None,
        "reason": reason or "بن دائمی",
        # source=manual از ورود اخراج‌های دستی به ریست اخراجی‌ها جلوگیری می‌کند.
        "source": source,
        "username_aliases": [],
    }

    for index, entry in enumerate(entries):
        if _entry_matches(entry, user_id, username, display_name):
            if isinstance(entry, dict):
                aliases = [
                    entry.get("username"),
                    *entry.get("username_aliases", []),
                ]
                record["username_aliases"] = sorted({
                    alias for alias in aliases
                    if alias and _normalise_identifier(alias)
                    != _normalise_identifier(username)
                })
            entries[index] = record
            save_banned(data)
            return

    entries.append(record)
    save_banned(data)


def remove_banned(group_id, user_id=None, username=None, display_name=None):
    """تمام رکوردهای منطبق با شناسه، نام و لقب کاربر را از فایل حذف می‌کند."""
    data = load_banned()
    gid = normalize_group_id(group_id)
    if gid not in data:
        return 0

    original_length = len(data[gid])
    data[gid] = [
        entry for entry in data[gid]
        if not _entry_matches(entry, user_id, username, display_name)
    ]
    removed_count = original_length - len(data[gid])
    if removed_count:
        save_banned(data)

    return removed_count


def find_banned_records(user_id=None, username=None, display_name=None, data=None):
    """تمام رکوردهای منطبق را در همهٔ گروه‌ها، از دادهٔ تازهٔ فایل پیدا می‌کند."""
    if data is None:
        data = load_banned()

    return {
        group_id: [
            entry for entry in entries
            if isinstance(entries, list)
            and _entry_matches(entry, user_id, username, display_name)
        ]
        for group_id, entries in data.items()
        if isinstance(entries, list)
        and any(
            _entry_matches(entry, user_id, username, display_name)
            for entry in entries
        )
    }


def remove_banned_everywhere(user_id=None, username=None, display_name=None):
    """تمام رکوردهای بنِ یک کاربر را در همهٔ گروه‌های فایل حذف می‌کند."""
    data = load_banned()
    before_records = find_banned_records(
        user_id, username, display_name, data
    )
    username_aliases = {
        alias
        for entries in before_records.values()
        for entry in entries
        if isinstance(entry, dict)
        for alias in [entry.get("username"), *entry.get("username_aliases", [])]
        if alias
    }
    removed_count = 0

    for group_id, entries in data.items():
        if not isinstance(entries, list):
            continue
        remaining = [
            entry for entry in entries
            if not _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
        ]
        removed_count += len(entries) - len(remaining)
        data[group_id] = remaining

    if removed_count:
        save_banned(data)

    fresh_data = load_banned()
    remaining_records = {
        group_id: [
            entry for entry in entries
            if isinstance(entries, list)
            and _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
        ]
        for group_id, entries in fresh_data.items()
        if isinstance(entries, list)
        and any(
            _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
            for entry in entries
        )
    }
    return removed_count, before_records, remaining_records


def get_matching_ban_records(group_id, user_id, username=None, data=None):
    """رکوردهای دقیقِ گروهی را که باعث تشخیص بن می‌شوند برمی‌گرداند."""
    if data is None:
        data = load_banned()
    return [
        entry for entry in data.get(normalize_group_id(group_id), [])
        if _entry_matches(entry, user_id, username)
    ]


def is_banned(group_id, user_id, username=None, data=None):
    """وضعیت بن را با دادهٔ تازهٔ فایل یا دادهٔ صریحِ داده‌شده بررسی می‌کند."""
    records = get_matching_ban_records(group_id, user_id, username, data)
    banned = bool(records)
    if banned:
        # فقط خلاصه چاپ می‌شود؛ dump کامل رکوردها روی مسیر داغ پیام،
        # فشار I/O بی‌دلیل ایجاد می‌کرد. منطق تشخیص بن تغییری نکرده.
        print(
            "BANNED STORAGE MATCH "
            f"user_id={user_id} username={username} group_id={group_id} "
            f"records_count={len(records)}"
        )
    return banned
