"""💰 سیستم اقتصاد — ماژول کاملاً مستقل.

این بسته هیچ وابستگی‌ای به بازی‌ها یا قابلیت‌های فعلی ربات ندارد و هیچ
فایل موجود را تغییر نمی‌دهد. بازی‌ها *فقط* از توابع همین فایل استفاده
می‌کنند و هرگز نباید مستقیماً فایل دیتابیس را باز کنند.

    from economy import add_bronze, get_balance

    add_bronze(user_id, 5, reference="riddle:42")

ساختار:
    economy/settings.py        ارزش سکه‌ها و نرخ تبدیل (قابل تنظیم)
    economy/storage.py         تراکنش اتمیک + نوشتن اتمیک روی دیسک
    economy/coins/             موجودی، تبدیل، انتقال
    economy/shop/              فروشگاه
    economy/ranking/           رتبه‌بندی بر پایهٔ ارزش کل
    economy/transactions/      تاریخچه
"""
from economy import ranking as _ranking
from economy import settings, shop, storage
from economy.coins import accounts as _accounts
from economy.coins.accounts import (
    BRONZE,
    COIN_TYPES,
    GOLD,
    SILVER,
    EconomyError,
    add,
    add_bronze,
    add_gold,
    add_silver,
    calculate_total_value,
    convert_bronze,
    convert_silver,
    get_balance,
    recalculate,
    recalculate_all,
    remove,
    remove_bronze,
    remove_gold,
    remove_silver,
    transfer,
)
from economy.daily import claim_daily, daily_status
from economy.ranking.board import get_rank, leaderboard, ranked_users
from economy.transactions.ledger import history as transaction_history

__all__ = [
    # انواع سکه
    "BRONZE", "SILVER", "GOLD", "COIN_TYPES", "EconomyError",
    # افزودن و کسر
    "add", "add_bronze", "add_silver", "add_gold",
    "remove", "remove_bronze", "remove_silver", "remove_gold",
    # تبدیل و انتقال
    "convert_bronze", "convert_silver", "transfer",
    # ارزش و موجودی
    "get_balance", "calculate_total_value", "recalculate", "recalculate_all",
    # رتبه‌بندی
    "get_rank", "leaderboard", "ranked_users",
    # جایزهٔ روزانه
    "claim_daily", "daily_status",
    # تاریخچه و فروشگاه
    "transaction_history", "shop",
    # زیرساخت
    "settings", "storage",
]


# ---------------------------------------------------------------------------
# API مخصوص بازی‌ها
# ---------------------------------------------------------------------------
def award(user_id, amount, coin_type=BRONZE, *, reference=None, note=None):
    """تنها راه پرداخت جایزه از سمت بازی‌ها.

    ``reference`` یکتا بدهید (مثل ``"vampire:chat:session"``) تا یک جایزه
    هرگز دو بار پرداخت نشود.
    """
    return _accounts.add(
        user_id, coin_type, amount,
        kind="reward", reference=reference, note=note,
    )


def spend(user_id, amount, coin_type=BRONZE, *, reference=None, note=None):
    """کسر سکه برای بازی‌ها؛ در صورت کمبود موجودی خطا می‌دهد."""
    return _accounts.remove(
        user_id, coin_type, amount,
        kind="spend", reference=reference, note=note,
    )


def reset_all():
    """پاک‌سازی کامل اقتصاد — فقط برای تست."""
    storage.reset_all()
    settings.reset_cache()
    shop.store._cache = None
    shop.store._cache_mtime = None
