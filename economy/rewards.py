"""🏆 جدول واحد جایزهٔ بازی‌ها.

تنها جایی که «هر بازی چقدر و چه نوع سکه‌ای می‌دهد» تعریف می‌شود. هر
بازی باید از همین‌جا بخواند تا هیچ بازی‌ای بدون جایزه یا با نوع اشتباه
سکه ثبت نشود.

قاعده:
    بازی‌های عادی → 🥉 برنز
    بازی‌های سخت  → 🥈 نقره

مقدار سکه‌ها همان مقدار قبلی است؛ فقط نوع سکهٔ بازی‌های سخت عوض شده.
"""
from economy import settings

BRONZE = settings.BRONZE
SILVER = settings.SILVER

# بازی‌های سخت: چند مرحله‌ای، رقابتی یا نیازمند استدلال گروهی.
HARD_GAMES = frozenset({"survival", "vampire"})

# (شناسه، مقدار، نوع سکه، نام فارسی)
_REWARDS = {
    # --- بازی‌های عادی → برنز -------------------------------------------
    "riddle":          (3, BRONZE, "حدس چیستان"),
    "emoji":           (4, BRONZE, "حدس ایموجی"),
    "flag":            (3, BRONZE, "حدس پرچم"),
    "name_family":     (6, BRONZE, "اسم فامیل"),
    "correction":      (1, BRONZE, "تصحیح کلمات"),
    "quiz":            (3, BRONZE, "چهار گزینه‌ای"),
    "fill_blank":      (2, BRONZE, "جای خالی"),
    "laugh_or_lose":   (1, BRONZE, "بخند یا بباز"),
    "lucky_box":       (0, BRONZE, "جعبه شانسی"),   # مقدار متغیر است
    # --- بازی‌های سخت → نقره --------------------------------------------
    "survival":        (8, SILVER, "بقا"),
    "survival_step":   (1, SILVER, "بقا — پاسخ صحیح"),
    "vampire":         (7, SILVER, "خون‌آشام"),
}

# جایزهٔ رتبهٔ روزانه (برنز، مثل قبل).
DAILY_RANK_REWARDS = (12, 8, 5)


class UnknownGame(KeyError):
    """بازی‌ای که در جدول جایزه ثبت نشده است."""


def _entry(game):
    try:
        return _REWARDS[game]
    except KeyError:
        raise UnknownGame(
            f"بازی {game!r} در جدول جایزه ثبت نشده است. "
            "هر بازی باید در economy/rewards.py تعریف شود."
        ) from None


def amount_for(game):
    """مقدار سکهٔ این بازی."""
    return _entry(game)[0]


def coin_for(game):
    """نوع سکهٔ این بازی: برنز برای عادی، نقره برای سخت."""
    return _entry(game)[1]


def label_for(game):
    """نام فارسی بازی، برای ثبت در تاریخچه."""
    return _entry(game)[2]


def is_hard(game):
    return coin_for(game) == SILVER


def coin_name(coin_type):
    return "نقره" if coin_type == SILVER else "برنز"


def games():
    """همهٔ شناسه‌های ثبت‌شده."""
    return tuple(_REWARDS)
