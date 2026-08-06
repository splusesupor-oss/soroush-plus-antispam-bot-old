"""🔐 ابزارهای مدیریتی جدید — لاگ مدیریتی + پاکسازی خودکار + کمکی‌ها.

این ماژول کاملاً مستقل است و فقط از سیستم‌های موجود (admin_storage،
owner_check، group_actions) استفاده می‌کند؛ چیزی از معماری قبلی را تغییر
نمی‌دهد.

دو دادهٔ ماندگار دارد:
  - ``config/admin_log.json``   → لاگِ اقداماتِ مدیریتی به تفکیکِ گروه.
  - ``config/auto_cleanup.json`` → تنظیماتِ پاکسازیِ خودکار به تفکیکِ گروه.

قانونِ حریم خصوصی: در هیچ خروجیِ قابلِ مشاهده، شناسهٔ عددیِ کاربر
نمایش داده نمی‌شود؛ همیشه از @username یا نامِ نمایشی یا «کاربر ناشناس»
استفاده می‌شود.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from modules.owner_check import is_global_owner
from modules.admin_storage import is_admin
from modules.group_storage import get_group_owner

_BASE = Path(__file__).resolve().parent.parent / "config"
_ADMIN_LOG_FILE = _BASE / "admin_log.json"
_CLEANUP_FILE = _BASE / "auto_cleanup.json"

# حداکثر تعداد لاگِ نگه‌داشته‌شده برای هر گروه (تا فایل بی‌نهایت رشد نکند).
MAX_LOG_PER_GROUP = 200


# ---------------------------------------------------------------------------
#  نمایشِ امنِ کاربر (هرگز شناسهٔ عددی)
# ---------------------------------------------------------------------------
def display_name(user):
    """@username یا نامِ نمایشی یا «کاربر ناشناس» — بدونِ ID عددی.

    ``user`` می‌تواند شیءِ کاملِ SPlusthon یا dict باشد.
    """
    username = None
    first = None
    last = None
    if isinstance(user, dict):
        username = user.get("username")
        first = user.get("first_name")
        last = user.get("last_name")
    elif user is not None:
        username = getattr(user, "username", None)
        first = getattr(user, "first_name", None)
        last = getattr(user, "last_name", None)

    uname = str(username or "").strip().lstrip("@")
    if uname and not uname.isdigit():
        return "@" + uname

    full = " ".join(part for part in (first, last) if part).strip()
    return full or "کاربر ناشناس"


def has_admin_permission(chat_id, user_id, username=None):
    """مالک اصلی ربات، مالک گروه، یا ادمینِ ثبت‌شدهٔ گروه."""
    if is_global_owner(user_id):
        return True
    owner = get_group_owner(chat_id)
    if owner is not None and str(user_id) == str(owner):
        return True
    return is_admin(chat_id, user_id, username)


def has_zero_permission(chat_id, user_id):
    """«صفر» فقط برای مالک اصلی ربات و مالک گروه؛ نه ادمینِ عادی."""
    if is_global_owner(user_id):
        return True
    owner = get_group_owner(chat_id)
    return owner is not None and str(user_id) == str(owner)


# ---------------------------------------------------------------------------
#  لاگ مدیریتی — ماندگار، به تفکیک گروه
# ---------------------------------------------------------------------------
def _load_admin_log():
    try:
        if _ADMIN_LOG_FILE.exists():
            data = json.loads(_ADMIN_LOG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _save_admin_log(data):
    try:
        _BASE.mkdir(parents=True, exist_ok=True)
        _ADMIN_LOG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def log_action(chat_id, actor, action, target=None, note=""):
    """یک اقدامِ مدیریتی را در لاگِ گروه ثبت می‌کند.

    ``actor``/``target`` می‌توانند شیءِ کاربر یا dict باشند.
    """
    key = str(chat_id)
    data = _load_admin_log()
    bucket = data.setdefault(key, [])
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "actor": display_name(actor),
        "action": action,
        "target": display_name(target) if target is not None else None,
        "note": note or "",
    }
    bucket.append(entry)
    if len(bucket) > MAX_LOG_PER_GROUP:
        del bucket[:-MAX_LOG_PER_GROUP]
    _save_admin_log(data)
    return entry


def get_log(chat_id, limit=30):
    """آخرین لاگ‌های این گروه (جدیدترین‌ها اول)."""
    data = _load_admin_log()
    bucket = data.get(str(chat_id), [])
    return list(reversed(bucket[-limit:]))


def clear_log(chat_id):
    data = _load_admin_log()
    data.pop(str(chat_id), None)
    _save_admin_log(data)


def format_log(chat_id, limit=30):
    """لاگ را به متنِ مرتب و خوانا تبدیل می‌کند."""
    entries = get_log(chat_id, limit)
    if not entries:
        return "📭 هنوز اقدامی در این گروه ثبت نشده است."
    lines = ["🧾 لاگ مدیریتی گروه:\n"]
    for i, e in enumerate(entries, 1):
        when = e.get("time", "")
        actor = e.get("actor", "کاربر ناشناس")
        action = e.get("action", "")
        target = e.get("target")
        note = e.get("note", "")
        if target:
            line = f"{i}. {when}\n   👤 {actor} → {action} ← {target}"
        else:
            line = f"{i}. {when}\n   👤 {actor} → {action}"
        if note:
            line += f"\n   📝 {note}"
        lines.append(line + "\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  پاکسازی خودکار — تنظیماتِ ماندگار + جریانِ مرحله‌به‌مرحله
# ---------------------------------------------------------------------------
# جریانِ مرحله‌به‌مرحله (در حافظه): chat_id -> مرحلهٔ انتظار
_PENDING_CLEANUP = {}  # chat_id -> {"step": "time"|"count", "time": "HH:MM"}


def _load_cleanups():
    try:
        if _CLEANUP_FILE.exists():
            data = json.loads(_CLEANUP_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _save_cleanups(data):
    try:
        _BASE.mkdir(parents=True, exist_ok=True)
        _CLEANUP_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def set_cleanup(chat_id, time_str, count):
    """تنظیماتِ پاکسازیِ این گروه را ذخیره می‌کند (ماندگار)."""
    data = _load_cleanups()
    data[str(chat_id)] = {
        "time": time_str,
        "count": int(count),
        "last_run": None,
    }
    _save_cleanups(data)
    return data[str(chat_id)]


def get_cleanup(chat_id):
    return _load_cleanups().get(str(chat_id))


def clear_cleanup(chat_id):
    data = _load_cleanups()
    data.pop(str(chat_id), None)
    _save_cleanups(data)


def all_cleanups():
    return _load_cleanups()


def mark_cleanup_run(chat_id, day):
    data = _load_cleanups()
    rec = data.get(str(chat_id))
    if rec:
        rec["last_run"] = day
        _save_cleanups(data)


def valid_time(value):
    """بررسیِ ساعتِ معتبر به شکل HH:MM."""
    value = (value or "").strip()
    try:
        hour, minute = value.split(":")
        hour, minute = int(hour), int(minute)
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def valid_count(value):
    """تعدادِ پیام: بین ۱ تا ۳۰۰۰."""
    try:
        n = int(str(value or "").strip().replace(",", "").replace("٬", ""))
    except (ValueError, AttributeError):
        return None
    if 1 <= n <= 3000:
        return n
    return None


# قفلِ مشترکِ per-group برایِ پاکسازی (دستی و خودکار با هم تداخل نکنند).
_GROUP_DELETE_LOCKS = {}


def get_group_lock(chat_id):
    lock = _GROUP_DELETE_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _GROUP_DELETE_LOCKS[chat_id] = lock
    return lock


async def execute_cleanup(bot, chat_id, count, logger=None):
    """اجرای پاکسازیِ خودکار برای یک گروه.

    ترتیب: قفل → اعلام → حذفِ دسته‌ای (۱۰۰تایی) → بازکردن → اعلامِ پایان.
    همه در یک تسکِ پس‌زمینه انجام می‌شود تا حلقهٔ پیام بلاک نشود.
    """
    def _log(msg):
        try:
            if logger is not None:
                logger.log_info(f"AUTO CLEANUP {msg}")
        except Exception:
            pass

    lock = get_group_lock(chat_id)
    if lock.locked():
        _log(f"SKIP chat_id={chat_id} reason=delete_in_progress")
        return
    async with lock:
        try:
            # ۱) قفلِ گروه
            try:
                await bot.group_actions.lock_group(chat_id)
            except Exception as e:
                _log(f"LOCK FAILED chat_id={chat_id} error={e!r}")
            try:
                await bot.client.send_message(
                    chat_id,
                    "🔒 گروه برای پاکسازی خودکار قفل شد.\n\n🧹 آغاز پاکسازی...",
                )
            except Exception:
                pass

            # ۲) جمع‌آوری و حذفِ دسته‌ایِ پیام‌ها (حداکثر ۱۰۰ در هر درخواست)
            deleted = 0
            fetched = 0
            while fetched < count:
                remaining = count - fetched
                limit = min(100, remaining)
                try:
                    messages = await bot.client.get_messages(
                        chat_id, limit=limit)
                except Exception as e:
                    _log(f"GET FAILED chat_id={chat_id} error={e!r}")
                    break
                ids = [m.id for m in messages if getattr(m, "id", None)]
                if not ids:
                    break
                fetched += len(ids)
                try:
                    await bot.client.delete_messages(chat_id, ids)
                    deleted += len(ids)
                except Exception as e:
                    _log(f"DELETE FAILED chat_id={chat_id} error={e!r}")
                await asyncio.sleep(0.15)

            # ۳) بازکردنِ گروه
            try:
                await bot.group_actions.unlock_group(chat_id)
            except Exception as e:
                _log(f"UNLOCK FAILED chat_id={chat_id} error={e!r}")

            # ۴) اعلامِ پایان
            try:
                await bot.client.send_message(
                    chat_id,
                    "🔓 پاکسازی به پایان رسید و گروه دوباره باز شد.",
                )
            except Exception:
                pass

            log_action(chat_id, {"username": "system"},
                       "پاکسازی خودکار",
                       note=f"{deleted} پیام حذف شد")
            _log(f"DONE chat_id={chat_id} deleted={deleted}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log(f"FAILED chat_id={chat_id} error={e!r}")
            try:
                await bot.group_actions.unlock_group(chat_id)
            except Exception:
                pass


async def run_cleanup_watcher(bot, logger=None, interval=None):
    """حلقهٔ پس‌زمینه: در زمانِ تنظیم‌شده، پاکسازیِ هر گروه را اجرا می‌کند.

    هر ``interval`` ثانیه (پیش‌فرض ۳۰) بررسی می‌کند؛ دقیقاً در دقیقهٔ
    زمانِ ذخیره‌شده و فقط یک بار در روز اجرا می‌شود.
    """
    import asyncio
    delay = 30 if interval is None else interval
    while True:
        try:
            now = datetime.now()
            current = f"{now.hour:02d}:{now.minute:02d}"
            day = now.date().isoformat()
            for key, rec in list(all_cleanups().items()):
                if rec.get("last_run") == day:
                    continue
                if rec.get("time") != current:
                    continue
                try:
                    chat_id = int(key)
                except (TypeError, ValueError):
                    chat_id = key
                mark_cleanup_run(chat_id, day)
                task = asyncio.create_task(
                    execute_cleanup(
                        bot, chat_id, int(rec.get("count", 0)),
                        logger=logger))
                try:
                    getattr(bot, "cleanup_tasks", {}).setdefault(
                        chat_id, set()).add(task)
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            try:
                if logger is not None:
                    logger.log_error(f"AUTO CLEANUP WATCHER FAILED {error!r}")
            except Exception:
                pass
        await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
#  ایجادِ تماسِ گروهی — با API واقعیِ SPlusthon
# ---------------------------------------------------------------------------
def _extract_group_call(result):
    """از نتیجهٔ CreateGroupCallRequest، شیءِ GroupCall (id+access_hash) را می‌یابد."""
    from splusthon.tl import types
    # اگر مستقیم GroupCall برگردد
    if hasattr(result, "id") and hasattr(result, "access_hash"):
        return result
    # UpdateGroupCall را در داخل Updates پیدا کن
    for attr in ("updates", "updates_list", "new_updates"):
        updates = getattr(result, attr, None)
        if not updates:
            continue
        for u in updates:
            if isinstance(u, types.UpdateGroupCall):
                call = getattr(u, "call", None)
                if call is not None and getattr(call, "id", None):
                    return call
    return None


async def create_group_call(client, chat_id, title="تماس گروهی"):
    """یک تماسِ گروهی ایجاد و لینکِ ورود به آن را برمی‌گرداند.

    از API واقعیِ SPlusthon استفاده می‌کند:
      phone.CreateGroupCallRequest  → ساختِ تماس
      phone.ExportGroupCallInviteRequest → لینکِ دعوت

    اگر سرورِ سروش این قابلیت را پشتیبانی نکند، RPC خطا می‌دهد که همان
    به کاربر گزارش می‌شود (هیچ پیاده‌سازیِ جعلی‌ای نیست).
    برمی‌گرداند ``(link, error)``.
    """
    from splusthon.tl import functions, types
    try:
        peer = await client.get_input_entity(chat_id)
        result = await client(functions.phone.CreateGroupCallRequest(
            peer=peer, title=title))
        call = _extract_group_call(result)
        if call is None:
            return None, ("تماس ایجاد شد اما سرور شناسهٔ تماس را برنگرداند؛ "
                          "شاید سروش‌پلاس این قابلیت را کامل پشتیبانی نمی‌کند.")
        invite = await client(functions.phone.ExportGroupCallInviteRequest(
            call=types.InputGroupCall(id=call.id, access_hash=call.access_hash)))
        link = getattr(invite, "link", None) or ""
        if not link:
            return None, "لینکِ تماس از سرور دریافت نشد."
        return link, None
    except Exception as e:
        name = e.__class__.__name__
        return None, (
            f"ایجاد تماس گروهی در این گروه ممکن نشد "
            f"({name}). سروش‌پلاس این قابلیت را پشتیبانی نمی‌کند یا "
            f"دسترسی لازم نیست. جزئیات: {e}")
