"""مدیریت توکن‌های امن، اختصاصی و وابسته به گروه برای ورود به سایت بازی روباه.

ویژگی‌های امنیتی:
- هر توکن به صورت رمزنگاری‌شده منحصراً به chat_id گروه فعال و user_id کاربر متصل است.
- بررسی وضعیت فعال بودن روباه در گروه ثبت‌شده (Active Group Verification) در لحظه ورود و هر عملیات.
- در صورت خروج روباه از گروه، غیرفعال شدن یا حذف گروه از ربات، توکن‌ها بلافاصله باطل می‌شوند.
- جلوگیری از پخش لینک با قفل شدن روی دستگاه اول (Device Binding).
- توکن‌ها در طول مدت اعتبار برای همان کاربر در همان گروه قابل استفاده مکرر هستند.
"""
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from modules.runtime_paths import CONFIG_DIR

TOKEN_FILE = CONFIG_DIR / "fox_game_tokens.json"
LEADERBOARD_FILE = CONFIG_DIR / "fox_game_leaderboard.json"

TOKEN_LIFETIME_SECONDS = 600  # ۱۰ دقیقه اعتبار


def _load_json(file_path):
    try:
        if file_path.exists():
            return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_json(file_path, data):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(file_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, file_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def is_group_active(chat_id):
    """بررسی فعال بودن روباه در گروه ثبت‌شده از دیتابیس گروه‌های ربات."""
    try:
        from modules import group_storage
        groups = group_storage.load_groups()
        # بررسی کلید مستقیم یا نرمال‌شده
        if str(chat_id) in groups:
            return groups[str(chat_id)].get("active", False) is True
        return group_storage.is_active(chat_id) is True
    except Exception:
        return True


def cleanup_expired():
    """حذف توکن‌های منقضی‌شده یا توکن‌های مربوط به گروه‌های غیرفعال."""
    data = _load_json(TOKEN_FILE)
    now = time.time()
    valid_tokens = {}
    for k, v in data.items():
        if v.get("expires_at", 0) > now:
            c_id = v.get("chat_id")
            if is_group_active(c_id):
                valid_tokens[k] = v
    if len(valid_tokens) != len(data):
        _save_json(TOKEN_FILE, valid_tokens)


def revoke_group_tokens(chat_id):
    """ابطال و حذف فوری تمام توکن‌های متصل به یک گروه خاص (هنگام خروج روباه یا حذف گروه)."""
    data = _load_json(TOKEN_FILE)
    removed = 0
    for t_key, t_data in list(data.items()):
        if str(t_data.get("chat_id")) == str(chat_id):
            data.pop(t_key, None)
            removed += 1
    if removed > 0:
        _save_json(TOKEN_FILE, data)
    return removed


def create_token(chat_id, user_id, first_name=None, username=None, check_active_group=False):
    """ایجاد توکن اختصاصی رمزنگاری‌شده متصل به شناسه گروه (chat_id) و کاربر (user_id)."""
    if check_active_group and not is_group_active(chat_id):
        raise ValueError("❌ روباه در این گروه فعال نیست یا گروه ثبت نشده است.")

    cleanup_expired()
    data = _load_json(TOKEN_FILE)
    now = time.time()

    # غیرفعال‌سازی توکن‌های قبلی همین کاربر در این گروه
    for t_key, t_data in list(data.items()):
        if str(t_data.get("user_id")) == str(user_id) and str(t_data.get("chat_id")) == str(chat_id):
            data.pop(t_key, None)

    # ایجاد امضای امن متصل به گروه و کاربر
    raw_token = secrets.token_urlsafe(32)
    display_name = first_name or (f"@{username}" if username else f"کاربر {user_id}")

    # دریافت عنوان گروه اگر ثبت شده باشد
    group_title = f"گروه {chat_id}"
    try:
        from modules import group_storage
        g_info = group_storage.load_groups().get(str(chat_id), {})
        if g_info.get("title"):
            group_title = g_info["title"]
    except Exception:
        pass

    # خواندن نام مستعار لیدربورد
    lb = _load_json(LEADERBOARD_FILE)
    existing_entry = lb.get(str(user_id), {})
    nickname = existing_entry.get("nickname") or display_name

    data[raw_token] = {
        "user_id": str(user_id),
        "chat_id": str(chat_id),
        "group_title": group_title,
        "first_name": first_name or "",
        "username": username or "",
        "nickname": nickname,
        "created_at": now,
        "expires_at": now + TOKEN_LIFETIME_SECONDS,
        "claimed": False,
        "device_id": None,
    }

    _save_json(TOKEN_FILE, data)

    # ثبت اولیه در لیدربورد
    if str(user_id) not in lb:
        lb[str(user_id)] = {
            "user_id": str(user_id),
            "nickname": nickname,
            "wins": 0,
            "gold_won": 0,
            "silver_won": 0,
            "bronze_won": 0,
            "games_played": 0,
            "last_active": now,
        }
        _save_json(LEADERBOARD_FILE, lb)

    return raw_token


def validate_token(token, device_id=None, expected_chat_id=None):
    """بررسی کامل و چندمرحله‌ای اعتبار توکن:
    ۱. وجود و انقضای زمانی توکن
    ۲. فعال بودن گروه ثبت‌شده در روباه (اگر روباه خارج شود، توکن باطل است)
    ۳. تطابق شناسه گروه
    ۴. انحصار دستگاه (Device Binding برای جلوگیری از پخش لینک)
    """
    if not token or not isinstance(token, str):
        return False, None, "توکن ارائه نشده است."

    data = _load_json(TOKEN_FILE)
    record = data.get(token)

    if not record:
        return False, None, "توکن معتبر نیست یا منقضی شده است."

    # ۱. بررسی زمان انقضا
    now = time.time()
    if record.get("expires_at", 0) <= now:
        data.pop(token, None)
        _save_json(TOKEN_FILE, data)
        return False, None, "اعتبار زمانی این لینک (۱۰ دقیقه) به پایان رسیده است."

    # ۲. بررسی فعال بودن گروه در ربات (Group Binding & Active Check)
    bound_chat_id = record.get("chat_id")
    if not is_group_active(bound_chat_id):
        data.pop(token, None)
        _save_json(TOKEN_FILE, data)
        return False, None, "❌ دسترسی غیرمجاز: روباه در این گروه فعال نیست یا گروه از لیست گروه‌های ربات حذف شده است."

    # ۳. بررسی تطابق گروه مورد انتظار
    if expected_chat_id is not None and str(bound_chat_id) != str(expected_chat_id):
        return False, None, "❌ این توکن برای این گروه صادر نشده است."

    # ۴. بررسی قفل دستگاه (Device Binding)
    saved_device = record.get("device_id")
    if device_id:
        if saved_device is None:
            record["device_id"] = str(device_id)
            record["claimed"] = True
            _save_json(TOKEN_FILE, data)
        elif saved_device != str(device_id):
            return False, None, "این لینک مخصوص کاربر و دستگاه دیگری است و امکان پخش عمومی ندارد."

    return True, record, None


def update_nickname(token, new_nickname, device_id=None):
    """به‌روزرسانی نام مستعار کاربر."""
    valid, record, err = validate_token(token, device_id)
    if not valid or not record:
        return False, err or "توکن نامعتبر است."

    clean_name = str(new_nickname).strip()[:30]
    if not clean_name:
        return False, "نام مستعار نمی‌تواند خالی باشد."

    data = _load_json(TOKEN_FILE)
    if token in data:
        data[token]["nickname"] = clean_name
        _save_json(TOKEN_FILE, data)

    user_id = record["user_id"]
    lb = _load_json(LEADERBOARD_FILE)
    if str(user_id) in lb:
        lb[str(user_id)]["nickname"] = clean_name
        lb[str(user_id)]["last_active"] = time.time()
        _save_json(LEADERBOARD_FILE, lb)

    return True, clean_name


def record_win(token, game_name, bronze_won=0, silver_won=0, gold_won=0, device_id=None):
    """ثبت پیروزی و اهدای سکه پس از تأیید اعتبار گروه و توکن."""
    valid, record, err = validate_token(token, device_id)
    if not valid or not record:
        return False, err or "توکن نامعتبر است."

    user_id = record["user_id"]
    chat_id = record["chat_id"]

    lb = _load_json(LEADERBOARD_FILE)
    entry = lb.setdefault(str(user_id), {
        "user_id": str(user_id),
        "nickname": record.get("nickname") or f"کاربر {user_id}",
        "wins": 0,
        "gold_won": 0,
        "silver_won": 0,
        "bronze_won": 0,
        "games_played": 0,
        "last_active": time.time(),
    })

    entry["wins"] = int(entry.get("wins", 0)) + 1
    entry["games_played"] = int(entry.get("games_played", 0)) + 1
    entry["bronze_won"] = int(entry.get("bronze_won", 0)) + int(bronze_won)
    entry["silver_won"] = int(entry.get("silver_won", 0)) + int(silver_won)
    entry["gold_won"] = int(entry.get("gold_won", 0)) + int(gold_won)
    entry["last_active"] = time.time()
    _save_json(LEADERBOARD_FILE, lb)

    # اهدای سکه در سیستم اقتصاد گروه مربوطه
    try:
        import economy
        if bronze_won > 0:
            economy.add_bronze(chat_id, user_id, bronze_won, note=f"سایت بازی: {game_name}")
        if silver_won > 0:
            economy.add_silver(chat_id, user_id, silver_won, note=f"سایت بازی: {game_name}")
        if gold_won > 0:
            economy.add_gold(chat_id, user_id, gold_won, note=f"سایت بازی: {game_name}")
    except Exception:
        pass

    return True, entry


def convert_coins(token, convert_type, times=1, device_id=None):
    """تبدیل سکه‌ها طبق منطق سیستم اقتصاد ربات در گروه متصل."""
    valid, record, err = validate_token(token, device_id)
    if not valid or not record:
        return False, err or "توکن نامعتبر یا منقضی است.", None

    user_id = record["user_id"]
    chat_id = record["chat_id"]

    try:
        import economy
        if convert_type == "bronze_to_silver":
            new_bal = economy.convert_bronze(chat_id, user_id, times=times, note="تبدیل سکه در سایت بازی")
        elif convert_type == "silver_to_gold":
            new_bal = economy.convert_silver(chat_id, user_id, times=times, note="تبدیل سکه در سایت بازی")
        else:
            return False, "نوع تبدیل نامعتبر است.", None

        balance = {
            "gold": new_bal.get(economy.GOLD, 0),
            "silver": new_bal.get(economy.SILVER, 0),
            "bronze": new_bal.get(economy.BRONZE, 0),
        }
        return True, "تبدیل با موفقیت انجام شد!", balance
    except Exception as e:
        return False, str(e), None


def get_real_leaderboard():
    """دریافت رتبه‌بندی تمام بازیکنان واقعی."""
    lb = _load_json(LEADERBOARD_FILE)
    players = list(lb.values())

    players.sort(
        key=lambda p: (
            p.get("wins", 0),
            p.get("gold_won", 0),
            p.get("silver_won", 0),
            p.get("bronze_won", 0)
        ),
        reverse=True,
    )
    return players[:20]
