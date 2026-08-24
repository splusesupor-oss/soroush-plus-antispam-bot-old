"""مدیریت توکن‌های امن، اختصاصی و یک‌بار‌مصرف برای ورود به سایت بازی روباه.

ویژگی‌ها:
- تولید توکن تصادفی غیرقابل حدس (cryptographically secure).
- انقضای خودکار پس از ۱۰ دقیقه.
- قفل شدن روی دستگاه اول (Device Binding) برای جلوگیری از پخش لینک.
- اتصال مستقیم به شناسه کاربر در ربات (بدون افشای user_id در URL).
- ثبت و به‌روزرسانی نام مستعار و رتبه‌بندی زنده بازیکنان واقعی.
"""
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from modules.runtime_paths import CONFIG_DIR

TOKEN_FILE = CONFIG_DIR / "fox_game_tokens.json"
LEADERBOARD_FILE = CONFIG_DIR / "fox_game_leaderboard.json"

TOKEN_LIFETIME_SECONDS = 600  # 10 دقیقه


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


def cleanup_expired():
    """حذف توکن‌های منقضی‌شده."""
    data = _load_json(TOKEN_FILE)
    now = time.time()
    valid_tokens = {k: v for k, v in data.items() if v.get("expires_at", 0) > now}
    if len(valid_tokens) != len(data):
        _save_json(TOKEN_FILE, valid_tokens)


def create_token(chat_id, user_id, first_name=None, username=None):
    """ایجاد توکن اختصاصی ۱۰ دقیقه‌ای برای کاربر و لغو توکن‌های قبلی او."""
    cleanup_expired()
    data = _load_json(TOKEN_FILE)
    now = time.time()

    # غیرفعال‌سازی توکن‌های قبلی همین کاربر
    for t_key, t_data in list(data.items()):
        if str(t_data.get("user_id")) == str(user_id):
            data.pop(t_key, None)

    token = secrets.token_urlsafe(32)
    display_name = first_name or (f"@{username}" if username else f"کاربر {user_id}")

    # خواندن نام مستعار ذخیره‌شده از جدول رتبه‌بندی اگر وجود دارد
    lb = _load_json(LEADERBOARD_FILE)
    existing_entry = lb.get(str(user_id), {})
    nickname = existing_entry.get("nickname") or display_name

    data[token] = {
        "user_id": str(user_id),
        "chat_id": str(chat_id),
        "first_name": first_name or "",
        "username": username or "",
        "nickname": nickname,
        "created_at": now,
        "expires_at": now + TOKEN_LIFETIME_SECONDS,
        "claimed": False,
        "device_id": None,
    }

    _save_json(TOKEN_FILE, data)

    # ثبت اولیه در لیدربورد اگر موجود نباشد
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

    return token


def validate_token(token, device_id=None):
    """بررسی اعتبار توکن و انحصار آن برای همان دستگاه/کاربر.

    خروجی: (is_valid, user_data, error_message)
    """
    cleanup_expired()
    data = _load_json(TOKEN_FILE)
    record = data.get(token)

    if not record:
        return False, None, "توکن معتبر نیست یا منقضی شده است."

    now = time.time()
    if record.get("expires_at", 0) <= now:
        data.pop(token, None)
        _save_json(TOKEN_FILE, data)
        return False, None, "اعتبار این لینک (۱۰ دقیقه) به پایان رسیده است."

    # بررسی Device Binding (جلوگیری از استفاده دیگران در صورت پخش لینک)
    saved_device = record.get("device_id")
    if device_id:
        if saved_device is None:
            # اولین ورود با این دستگاه: قفل کردن لینک روی همین دستگاه
            record["device_id"] = str(device_id)
            record["claimed"] = True
            _save_json(TOKEN_FILE, data)
        elif saved_device != str(device_id):
            return False, None, "این لینک مخصوص کاربر و دستگاه دیگری است. لطفاً سایت بازی را از ربات خودتان دریافت کنید."

    return True, record, None


def update_nickname(token, new_nickname, device_id=None):
    """به‌روزرسانی نام مستعار کاربر."""
    valid, record, _ = validate_token(token, device_id)
    if not valid or not record:
        return False, "توکن نامعتبر است."

    clean_name = str(new_nickname).strip()[:30]
    if not clean_name:
        return False, "نام مستعار نمی‌تواند خالی باشد."

    # به‌روزرسانی در توکن
    data = _load_json(TOKEN_FILE)
    if token in data:
        data[token]["nickname"] = clean_name
        _save_json(TOKEN_FILE, data)

    # به‌روزرسانی در لیدربورد
    user_id = record["user_id"]
    lb = _load_json(LEADERBOARD_FILE)
    if str(user_id) in lb:
        lb[str(user_id)]["nickname"] = clean_name
        lb[str(user_id)]["last_active"] = time.time()
        _save_json(LEADERBOARD_FILE, lb)

    return True, clean_name


def record_win(token, game_name, bronze_won=0, silver_won=0, gold_won=0, device_id=None):
    """ثبت پیروزی و ارتقای رتبه در لیدربورد واقعی."""
    valid, record, _ = validate_token(token, device_id)
    if not valid or not record:
        return False, "توکن نامعتبر است."

    user_id = record["user_id"]
    chat_id = record["chat_id"]

    # ثبت در لیدربورد
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

    # اتصال به سیستم اقتصاد ربات برای اهدای واقعی سکه‌ها
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
    """تبدیل سکه‌ها طبق منطق سیستم اقتصاد ربات."""
    valid, record, _ = validate_token(token, device_id)
    if not valid or not record:
        return False, "توکن نامعتبر یا منقضی است.", None

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
    """دریافت رتبه‌بندی تمام بازیکنان واقعی (مرتب‌شده بر اساس بردها و سکه‌ها)."""
    lb = _load_json(LEADERBOARD_FILE)
    players = list(lb.values())

    # مرتب‌سازی بر اساس: تعداد برد، سپس سکه طلا، سپس نقره و برنز
    players.sort(
        key=lambda p: (
            p.get("wins", 0),
            p.get("gold_won", 0),
            p.get("silver_won", 0),
            p.get("bronze_won", 0)
        ),
        reverse=True,
    )
    return players[:20]  # ۲۰ بازیکن برتر واقعی
