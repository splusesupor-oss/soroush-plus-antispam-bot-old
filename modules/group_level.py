"""🏆 سطح گروه — یک سطح به ازای هر ۵۰۰ پیام، تا سقفِ سطح ۱۵.

ماژولِ کاملاً مستقل:

* شمارشِ پیام‌ها از سیستمِ موجودِ ``modules.group_stats`` خوانده می‌شود
  (فقط خواندن؛ چیزی در آن تغییر نمی‌کند).
* «آخرین سطحِ اعلام‌شده» در فایلِ جداگانهٔ ``config/group_level.json``
  نگه داشته می‌شود تا پیامِ تبریکِ ارتقا فقط یک بار فرستاده شود.
"""
import json
from pathlib import Path

from modules.group_id import normalize_group_id
from modules.group_stats import get_stats, top_users

_BASE = Path(__file__).resolve().parent.parent / "config"
_FILE = _BASE / "group_level.json"

COMMAND = "سطح گروه"

MESSAGES_PER_LEVEL = 500
MAX_LEVEL = 15

# کشِ درون‌حافظه‌ای تا مسیرِ داغِ پیام‌ها برایِ هر پیام فایل نخواند.
_MEM_LEVEL = {}

_PERSIAN_DIGITS = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"


def fa(value):
    return "".join(_PERSIAN_DIGITS[int(ch)] if ch.isdigit() else ch
                   for ch in str(value))


# ---------------------------------------------------------------------------
#  محاسبهٔ سطح
# ---------------------------------------------------------------------------
def level_for(messages):
    try:
        messages = max(0, int(messages))
    except (TypeError, ValueError):
        messages = 0
    return min(MAX_LEVEL, messages // MESSAGES_PER_LEVEL + 1)


def message_count(chat_id):
    stats = get_stats(chat_id) or {}
    try:
        return max(0, int(stats.get("messages", 0)))
    except (TypeError, ValueError):
        return 0


def progress(chat_id):
    """اطلاعاتِ کاملِ سطحِ گروه به‌صورت dict."""
    messages = message_count(chat_id)
    level = level_for(messages)
    if level >= MAX_LEVEL:
        needed = 0
        done = MESSAGES_PER_LEVEL
    else:
        needed = level * MESSAGES_PER_LEVEL - messages
        done = MESSAGES_PER_LEVEL - needed
    return {
        "messages": messages,
        "level": level,
        "max_level": MAX_LEVEL,
        "remaining": max(0, needed),
        "done": max(0, min(MESSAGES_PER_LEVEL, done)),
        "per_level": MESSAGES_PER_LEVEL,
        "top": top_member(chat_id),
    }


def top_member(chat_id):
    """فعال‌ترین عضوِ گروه → ``(display, messages)`` یا ``None``."""
    rows = top_users(chat_id, limit=1) or []
    if not rows:
        return None
    user_id, info = rows[0]
    if not isinstance(info, dict):
        return None
    count = info.get("messages", 0)
    if not count:
        return None
    username = str(info.get("username") or "").strip().lstrip("@")
    if username and not username.isdigit():
        display = "@" + username
    else:
        display = "کاربر ناشناس"
    return display, count


# ---------------------------------------------------------------------------
#  ذخیرهٔ آخرین سطحِ اعلام‌شده
# ---------------------------------------------------------------------------
def _load():
    try:
        if _FILE.exists():
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _save(data):
    try:
        _BASE.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def last_level(chat_id):
    data = _load()
    try:
        return int(data.get(normalize_group_id(chat_id), 0))
    except (TypeError, ValueError):
        return 0


def set_level(chat_id, level):
    data = _load()
    key = normalize_group_id(chat_id)
    data[key] = int(level)
    _MEM_LEVEL[key] = int(level)
    _save(data)


def maybe_level_up(chat_id):
    """نسخهٔ سبکِ ``check_level_up`` برای مسیرِ داغِ هر پیام.

    فقط وقتی سطحِ محاسبه‌شده با سطحِ کش‌شده فرق کند سراغِ دیسک می‌رود؛
    در بقیهٔ پیام‌ها هزینه‌اش یک خواندنِ کشِ ``group_stats`` است.
    """
    key = normalize_group_id(chat_id)
    level = level_for(message_count(chat_id))
    if _MEM_LEVEL.get(key) == level:
        return None
    _MEM_LEVEL[key] = level
    return check_level_up(chat_id)


def check_level_up(chat_id):
    """اگر گروه تازه ارتقا یافته باشد، متنِ تبریک را برمی‌گرداند.

    در غیر این صورت ``None``. سطحِ جدید بلافاصله ذخیره می‌شود تا پیام
    فقط یک بار فرستاده شود.
    """
    info = progress(chat_id)
    level = info["level"]
    previous = last_level(chat_id)
    if previous == 0:
        # اولین بار: فقط ثبت می‌شود، تبریک الکی فرستاده نمی‌شود.
        set_level(chat_id, level)
        return None
    if level <= previous:
        return None
    set_level(chat_id, level)
    return congrats_text(info)


def reset(chat_id=None):
    if chat_id is None:
        _MEM_LEVEL.clear()
        _save({})
        return True
    key = normalize_group_id(chat_id)
    _MEM_LEVEL.pop(key, None)
    data = _load()
    if data.pop(key, None) is None:
        return False
    _save(data)
    return True


# ---------------------------------------------------------------------------
#  متن‌ها
# ---------------------------------------------------------------------------
def _bar(info):
    filled = int(round(info["done"] / info["per_level"] * 10))
    filled = max(0, min(10, filled))
    return "▰" * filled + "▱" * (10 - filled)


def congrats_text(info=None, chat_id=None):
    if info is None:
        info = progress(chat_id)
    lines = [
        "🎉 تبریک! سطح گروه ارتقا پیدا کرد.\n\n",
        f"🏆 سطح جدید گروه: {fa(info['level'])} از {fa(info['max_level'])}\n",
        f"💬 مجموع پیام‌ها: {fa(info['messages'])}\n",
    ]
    top = info.get("top")
    if top:
        lines.append(f"👑 فعال‌ترین عضو: {top[0]} با {fa(top[1])} پیام\n")
    if info["level"] >= info["max_level"]:
        lines.append("\n🌟 گروه به بالاترین سطح رسیده است!")
    else:
        lines.append(
            f"\n📈 تا سطح بعدی {fa(info['remaining'])} پیام مانده.")
    return "".join(lines)


def format_level(chat_id):
    """پاسخِ دستورِ «سطح گروه» → ``(text, bold_lines)``."""
    info = progress(chat_id)
    lines = [
        "🏆 سطح گروه\n\n",
        f"📊 سطح فعلی: {fa(info['level'])} از {fa(info['max_level'])}\n",
        f"💬 مجموع پیام‌ها: {fa(info['messages'])}\n",
        f"🧮 هر {fa(info['per_level'])} پیام = یک سطح\n\n",
    ]
    top = info.get("top")
    if top:
        lines.append(f"👑 فعال‌ترین عضو گروه:\n{top[0]} — "
                     f"{fa(top[1])} پیام\n\n")
    else:
        lines.append("👑 فعال‌ترین عضو گروه: هنوز ثبت نشده\n\n")
    lines.append(f"{_bar(info)}\n")
    if info["level"] >= info["max_level"]:
        lines.append("🌟 این گروه به بالاترین سطح (۱۵) رسیده است!")
    else:
        lines.append(
            f"📈 تا سطح {fa(info['level'] + 1)} فقط "
            f"{fa(info['remaining'])} پیام مانده.")
    return "".join(lines)
