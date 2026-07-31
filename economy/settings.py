"""⚙️ تنظیمات سیستم اقتصاد.

ارزش هر سکه و نرخ‌های تبدیل داخل کد ثابت نیستند؛ در
``config/economy_settings.json`` ذخیره می‌شوند تا بعداً بدون تغییر کد
قابل ویرایش باشند.
"""
import json
import os
import tempfile
from pathlib import Path

SETTINGS_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "economy_settings.json"
)

BRONZE = "bronze"
SILVER = "silver"
GOLD = "gold"
COIN_TYPES = (BRONZE, SILVER, GOLD)

COIN_LABELS = {
    BRONZE: "🥉 سکه برنز",
    SILVER: "🥈 سکه نقره",
    GOLD: "🥇 سکه طلا",
}

DEFAULTS = {
    # ارزش هر واحد از هر سکه. total_coin_value از همین‌ها ساخته می‌شود.
    "BronzeValue": 1,
    "SilverValue": 10,
    "GoldValue": 100,
    # نرخ تبدیل: ۱۰۰ برنز ➜ ۱۰ نقره، ۷۰ نقره ➜ ۱۰ طلا.
    "BronzeToSilverCost": 100,
    "BronzeToSilverGain": 10,
    "SilverToGoldCost": 70,
    "SilverToGoldGain": 10,
    # جایزهٔ روزانه.
    "DailyRewardBronze": 25,
    "DailyRewardSilver": 0,
    "DailyRewardGold": 0,
    "DailyRewardCooldownSeconds": 24 * 60 * 60,
}

_cache = None
_cache_mtime = None


def _mtime():
    try:
        return SETTINGS_FILE.stat().st_mtime_ns
    except OSError:
        return None


def _atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load():
    """تنظیمات فعلی؛ کلیدهای جاافتاده با مقدار پیش‌فرض پر می‌شوند."""
    global _cache, _cache_mtime
    mtime = _mtime()
    if _cache is not None and mtime == _cache_mtime:
        return dict(_cache)

    data = dict(DEFAULTS)
    if mtime is not None:
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key in DEFAULTS and isinstance(value, (int, float)):
                        data[key] = value
        except (OSError, ValueError):
            data = dict(DEFAULTS)
    _cache = data
    _cache_mtime = mtime
    return dict(data)


def save(values):
    """تنظیمات را روی دیسک می‌نویسد و کش را تازه می‌کند."""
    global _cache, _cache_mtime
    current = load()
    current.update({
        key: value for key, value in values.items()
        if key in DEFAULTS and isinstance(value, (int, float))
    })
    _atomic_write(SETTINGS_FILE, current)
    _cache = current
    _cache_mtime = _mtime()
    return dict(current)


def get(key, default=None):
    return load().get(key, DEFAULTS.get(key, default))


def coin_value(coin_type):
    """ارزش یک واحد از یک نوع سکه."""
    mapping = {
        BRONZE: "BronzeValue",
        SILVER: "SilverValue",
        GOLD: "GoldValue",
    }
    if coin_type not in mapping:
        raise ValueError(f"نوع سکه نامعتبر است: {coin_type!r}")
    return get(mapping[coin_type])


def coin_values():
    return {coin: coin_value(coin) for coin in COIN_TYPES}


def reset_cache():
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None
