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
# لاگ فقط برای ۲۴ ساعت نگه داشته می‌شود؛ قدیمی‌ترها خودکار حذف می‌شوند.
LOG_TTL_SECONDS = 24 * 60 * 60


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


def _prune_log(data):
    """لاگ‌های قدیمی‌تر از ۲۴ ساعت را از همهٔ گروه‌ها حذف و ذخیره می‌کند.

    برمی‌گرداند True اگر چیزی حذف شده باشد.
    """
    now = time.time()
    changed = False
    for key in list(data.keys()):
        bucket = data[key]
        if not isinstance(bucket, list):
            data.pop(key, None)
            changed = True
            continue
        kept = []
        for e in bucket:
            ts = e.get("_ts", 0)
            if ts and (now - ts) < LOG_TTL_SECONDS:
                kept.append(e)
            else:
                changed = True
        if kept:
            data[key] = kept
        else:
            data.pop(key, None)
            changed = True
    return changed


def log_action(chat_id, actor, action, target=None, note=""):
    """یک اقدامِ مدیریتی را در لاگِ گروه ثبت می‌کند.

    ``actor``/``target`` می‌توانند شیءِ کاربر یا dict باشند.
    """
    key = str(chat_id)
    data = _load_admin_log()
    bucket = data.setdefault(key, [])
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "_ts": time.time(),
        "actor": display_name(actor),
        "action": action,
        "target": display_name(target) if target is not None else None,
        "note": note or "",
    }
    bucket.append(entry)
    if len(bucket) > MAX_LOG_PER_GROUP:
        del bucket[:-MAX_LOG_PER_GROUP]
    # پس از افزودن، لاگ‌های قدیمی را هم پاک کن (خودکار).
    _prune_log(data)
    _save_admin_log(data)
    return entry


def get_log(chat_id, limit=30):
    """آخرین لاگ‌های ۲۴ ساعتِ اخیرِ این گروه (جدیدترین‌ها اول)."""
    data = _load_admin_log()
    if _prune_log(data):
        _save_admin_log(data)
    bucket = data.get(str(chat_id), [])
    return list(reversed(bucket[-limit:]))


def clear_log(chat_id):
    data = _load_admin_log()
    data.pop(str(chat_id), None)
    _save_admin_log(data)


def _u16_len(value):
    return len((value or "").encode("utf-16-le")) // 2


def format_log(chat_id, limit=30):
    """لاگ را به متنِ مرتب و خوانا + entityهای قالب‌بندی برمی‌گرداند.

    عملیاتِ پشتِ‌سرهمِ یک ادمین در یک «بخش» گروه‌بندی می‌شوند: نامِ ادمین
    فقط یک بار (داخلِ نقل‌قولِ شیشه‌ای) نمایش داده می‌شود و همهٔ عملیاتِ
    همان ادمین زیرِ همان بخش به‌صورتِ ردیفی می‌آیند. اگر ادمین عوض شد،
    بخشِ جدیدی ساخته می‌شود.

    خروجی ``(text, entities)``.
    """
    from splusthon.tl.types import MessageEntityBlockquote, MessageEntityBold

    entries = get_log(chat_id, limit)
    if not entries:
        return "📭 هنوز اقدامی در این گروه ثبت نشده است.", []

    # get_log جدیدترین‌ها را اول برمی‌گرداند؛ برایِ نمایشِ قدیمی‌ترین‌ها اول
    # (مطابقِ قالبِ خواسته‌شده) آن را برمی‌گردانیم.
    entries = list(reversed(entries))

    # گروه‌بندی: بخش‌هایِ پشت‌سرهمِ همان ادمین را یکی می‌کنیم.
    sections = []  # [(actor, time, [(action, note)])]
    for e in entries:
        actor = e.get("actor", "کاربر ناشناس")
        when = e.get("time", "")
        action = e.get("action", "")
        note = e.get("note", "")
        target = e.get("target")
        # اگر هدف (کاربرِ موردِ عملیات) موجود باشد به نمایشِ عملیات می‌چسبانیم.
        if target:
            action_text = f"{action} {target}"
        else:
            action_text = action
        if sections and sections[-1][0] == actor:
            sections[-1][2].append((action_text, note))
        else:
            sections.append((actor, when, [(action_text, note)]))

    lines = ["🧾 لاگ مدیریتی گروه:\n"]
    entities = []
    for idx, (actor, when, actions) in enumerate(sections, 1):
        lines.append(f"{idx}. {when}\n")
        # نامِ ادمین فقط یک بار، داخلِ نقل‌قولِ شیشه‌ای
        actor_line = f"👤 {actor}\n"
        actor_start = _u16_len("".join(lines))
        lines.append(actor_line)
        entities.append(MessageEntityBlockquote(
            offset=actor_start, length=_u16_len(actor_line)))
        # همهٔ عملیاتِ همین ادمین، ردیفی (خارج از نقل‌قول)
        for action, note in actions:
            lines.append(f"→ {action}\n")
            if note:
                lines.append(f"📝 {note}\n")
        lines.append("\n")

    # Footer Bold
    footer = "⏳ این لاگ‌ها هر ۲۴ ساعت به‌صورت خودکار ریست می‌شوند."
    footer_start = _u16_len("".join(lines))
    lines.append(footer)
    entities.append(MessageEntityBold(
        offset=footer_start, length=_u16_len(footer)))

    return "".join(lines), entities


# ---------------------------------------------------------------------------
#  پاکسازی خودکار — تنظیماتِ ماندگار + جریانِ مرحله‌به‌مرحله
# ---------------------------------------------------------------------------
# جریانِ مرحله‌به‌مرحله (در حافظه): chat_id -> مرحلهٔ انتظار
#   step: "day" | "time" | "count"
_PENDING_CLEANUP = {}  # chat_id -> {"step": ..., "day": "today"|"tomorrow",
#                       "time": "HH:MM", "user_id": ...}


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


def format_jalali(date):
    """تاریخِ میلادی را به شمسی به‌صورت «۱۴۰۵/۰۵/۱۵» برمی‌گرداند.

    الگوریتمِ استانداردِ تبدیلِ میلادی→شمسی.
    """
    g_y = date.year
    g_m = date.month
    g_d = date.day

    g_days_in_month = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    j_days_in_month = (31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)

    gy = g_y - 1600
    gm = g_m - 1
    gd = g_d - 1

    g_day_no = (365 * gy + (gy + 3) // 4 - (gy + 99) // 100
                + (gy + 399) // 400)
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        # leap year
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            break
        j_day_no -= j_days_in_month[i]
    jm = i + 1
    jd = j_day_no + 1
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def valid_day(value):
    """«امروز» یا «فردا» را تشخیص می‌دهد."""
    norm = (value or "").strip().replace("‌", "")
    if norm in ("امروز", "امرز", "اموز"):
        return "today"
    if norm in ("فردا", "فرداه", "فر دا"):
        return "tomorrow"
    return None


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


def time_of_day(hour):
    """برچسبِ بخشِ روز بر اساسِ ساعت: صبح/ظهر/عصر/شب."""
    if hour < 6:
        return "شب"
    if hour < 12:
        return "صبح"
    if hour < 16:
        return "ظهر"
    if hour < 19:
        return "عصر"
    return "شب"


def compute_scheduled_at(day, time_str, now=None):
    """زمانِ دقیقِ اجرایِ پاکسازی را محاسبه می‌کند.

    ``day``: "today" یا "tomorrow"؛ ``time_str``: "HH:MM".
    اگر زمانِ «امروز» گذشته باشد، به «فردا» منتقل می‌شود.
    خروجی: datetime (منطقهٔ محلی) یا None اگر نامعتبر.
    """
    if now is None:
        now = datetime.now()
    t = valid_time(time_str)
    if t is None:
        return None
    hour, minute = int(t.split(":")[0]), int(t.split(":")[1])

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if day == "tomorrow":
        target = target + timedelta(days=1)
    else:
        # «امروز» اما اگر ساعت گذشته → فردا
        if target <= now:
            target = target + timedelta(days=1)
    return target


def set_cleanup(chat_id, day, time_str, count):
    """تنظیماتِ پاکسازیِ این گروه را با زمانِ کامل ذخیره می‌کند (ماندگار)."""
    now = datetime.now()
    scheduled_at = compute_scheduled_at(day, time_str, now)
    if scheduled_at is None:
        return None
    data = _load_cleanups()
    data[str(chat_id)] = {
        "set_at": now.isoformat(timespec="seconds"),
        "scheduled_at": scheduled_at.isoformat(timespec="seconds"),
        "time": time_str,
        "day": day,
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


def mark_cleanup_run(chat_id, scheduled_at):
    data = _load_cleanups()
    rec = data.get(str(chat_id))
    if rec:
        rec["last_run"] = scheduled_at
        _save_cleanups(data)


def valid_count(value):
    """تعدادِ پیام: بین ۱ تا ۳۰۰۰."""
    try:
        n = int(str(value or "").strip().replace(",", "").replace("٬", ""))
    except (ValueError, AttributeError):
        return None
    if 1 <= n <= 3000:
        return n
    return None


def format_cleanup(chat_id):
    """نمایشِ خوانای تنظیماتِ پاکسازیِ این گروه.

    مثال:
      🕐 زمان تنظیم: امروز ساعت ۱۳:۳۰
      🧹 زمان پاکسازی: فردا ساعت ۰۱:۳۰
      🗑️ تعداد پیام: ۱۰۰
    """
    rec = get_cleanup(chat_id)
    if not rec:
        return "🧹 پاکسازی خودکاری برای این گروه تنظیم نشده است."

    try:
        set_at = datetime.fromisoformat(rec.get("set_at", ""))
    except (ValueError, TypeError):
        set_at = None
    try:
        sched = datetime.fromisoformat(rec.get("scheduled_at", ""))
    except (ValueError, TypeError):
        sched = None

    today = datetime.now()
    if set_at is not None:
        set_day = set_at.date() == today.date()
        set_label = f"{'امروز' if set_day else format_jalali(set_at.date())} " \
                    f"ساعت {set_at.strftime('%H:%M')}"
    else:
        set_label = "-"

    if sched is not None:
        diff_days = (sched.date() - today.date()).days
        if diff_days <= 0:
            day_label = "امروز"
        elif diff_days == 1:
            day_label = "فردا"
        else:
            day_label = format_jalali(sched.date())
        tod = time_of_day(sched.hour)
        sched_label = (f"{day_label} ساعت {sched.strftime('%H:%M')} "
                       f"({tod})")
    else:
        sched_label = "-"

    count = rec.get("count", 0)
    return (
        f"🧹 پاکسازی خودکار:\n\n"
        f"🕐 زمان تنظیم: {set_label}\n"
        f"🧹 زمان پاکسازی: {sched_label}\n"
        f"🗑️ تعداد پیام: {count}"
    )


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
    """حلقهٔ پس‌زمینه: دقیقاً در زمانِ ذخیره‌شده، پاکسازیِ هر گروه را اجرا می‌کند.

    هر ``interval`` ثانیه (پیش‌فرض ۳۰) بررسی می‌کند؛ اگر زمانِ اجرا رسیده و
    هنوز اجرا نشده باشد (``last_run`` برابرِ آن زمان نباشد)، اجرا می‌شود.
    """
    import asyncio
    delay = 30 if interval is None else interval
    while True:
        try:
            now = datetime.now()
            for key, rec in list(all_cleanups().items()):
                sched = rec.get("scheduled_at")
                if not sched:
                    continue
                try:
                    sched_dt = datetime.fromisoformat(sched)
                except (ValueError, TypeError):
                    continue
                # اگر هنوز زمان نرسیده → رد
                if now < sched_dt:
                    continue
                # اگر قبلاً اجرا شده → رد
                if rec.get("last_run") == sched:
                    continue
                try:
                    chat_id = int(key)
                except (TypeError, ValueError):
                    chat_id = key
                mark_cleanup_run(chat_id, sched)
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


_PERSIAN_WEEKDAYS = ("دوشنبه", "سه‌شنبه", "چهارشنبه",
                     "پنجشنبه", "جمعه", "شنبه", "یکشنبه")


def format_call_invite(call_title, creator_name, created_at, link):
    """پیامِ دعوتِ تماسِ گروهی را با فرمتِ کامل می‌سازد.

    اطلاعات واقعیِ تماس:
      - نامِ تماس (call_title)
      - سازندهٔ تماس (creator_name)
      - روز هفته + تاریخِ کاملِ ساخت (created_at)
      - لینکِ واقعیِ تماس (link)
    """
    # روز هفته (میلادی ۰=دوشنبه) → فارسی
    weekday = _PERSIAN_WEEKDAYS[created_at.weekday()]
    jalali = format_jalali(created_at.date())
    full_time = f"{weekday} {jalali} ساعت {created_at.strftime('%H:%M')}"
    text = (
        "شما به یک تماس گروهی دعوت شدید.\n\n"
        f"📞 نام تماس: «{call_title}»\n\n"
        f"😀 سازنده تماس: {creator_name}\n\n"
        f"⏰ زمان ساخت: {full_time}\n\n"
        "توجه، این یک لینک عمومی است و تمام کاربران سروش+ می‌توانند با "
        "وارد شدن به این لینک به تماس شما بپیوندند. در به اشتراک گذاشتن "
        "آن دقت کنید.\n\n"
        "🔗 لینک تماس:\n"
        f"{link}"
    )
    return text


async def create_group_call(client, chat_id, title="تماس گروهی"):
    """یک تماسِ گروهی ایجاد و لینکِ ورود به آن را برمی‌گرداند.

    از API واقعیِ SPlusthon استفاده می‌کند:
      phone.CreateGroupCallRequest  → ساختِ تماس
      phone.ExportGroupCallInviteRequest → لینکِ دعوت

    اگر سرورِ سروش این قابلیت را پشتیبانی نکند، RPC خطا می‌دهد که همان
    به کاربر گزارش می‌شود (هیچ پیاده‌سازیِ جعلی‌ای نیست).
    برمی‌گرداند ``(link, error, created_at)``.
    """
    from splusthon.tl import functions, types
    created_at = datetime.now()
    try:
        peer = await client.get_input_entity(chat_id)
        result = await client(functions.phone.CreateGroupCallRequest(
            peer=peer, title=title))
        call = _extract_group_call(result)
        if call is None:
            return None, ("تماس ایجاد شد اما سرور شناسهٔ تماس را برنگرداند؛ "
                          "شاید سروش‌پلاس این قابلیت را کامل پشتیبانی نمی‌کند."), created_at
        invite = await client(functions.phone.ExportGroupCallInviteRequest(
            call=types.InputGroupCall(id=call.id, access_hash=call.access_hash)))
        link = getattr(invite, "link", None) or ""
        if not link:
            return None, "لینکِ تماس از سرور دریافت نشد.", created_at
        return link, None, created_at
    except Exception as e:
        name = e.__class__.__name__
        return None, (
            f"ایجاد تماس گروهی در این گروه ممکن نشد "
            f"({name}). سروش‌پلاس این قابلیت را پشتیبانی نمی‌کند یا "
            f"دسترسی لازم نیست. جزئیات: {e}"), created_at
