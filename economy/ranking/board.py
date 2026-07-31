"""🏆 جدول رتبه‌بندی.

مرتب‌سازی *فقط* بر اساس ``total_coin_value`` است، نه تعداد سکه. اگر دو
کاربر ارزش برابر داشته باشند، کسی که زودتر به آن مقدار رسیده رتبهٔ
بالاتری می‌گیرد؛ این با ``value_reached_seq`` سنجیده می‌شود که یک
شمارندهٔ یکنواخت صعودی است و در لحظهٔ تغییر ارزش ثبت می‌گردد.
"""
from economy import storage
from economy.coins import accounts


def _rows():
    data = storage.snapshot()
    rows = []
    for key, user in data.get("users", {}).items():
        value = accounts.compute_total_value(user)
        rows.append({
            "user_id": key,
            "total_coin_value": value,
            "bronze": int(user.get(accounts.BRONZE, 0)),
            "silver": int(user.get(accounts.SILVER, 0)),
            "gold": int(user.get(accounts.GOLD, 0)),
            "name": user.get("name"),
            "wins": int(user.get("wins", 0)),
            "reached_seq": int(user.get("value_reached_seq", 0)),
            "reached_at": user.get("value_reached_at"),
        })
    return rows


def ranked_users(limit=None, include_zero=False):
    """همهٔ کاربران، مرتب‌شده از ارزشمندترین.

    ``include_zero=False`` کاربران با ارزش صفر را کنار می‌گذارد.
    """
    rows = _rows()
    if not include_zero:
        rows = [row for row in rows if row["total_coin_value"] > 0]
    # ارزش بیشتر بالاتر؛ در تساوی، مهر زمانی کوچک‌تر (زودتر) بالاتر.
    rows.sort(key=lambda row: (-row["total_coin_value"], row["reached_seq"]))
    for index, row in enumerate(rows, 1):
        row["rank"] = index
    return rows[:limit] if limit else rows


def leaderboard(limit=10, include_zero=False):
    return ranked_users(limit=limit, include_zero=include_zero)


def get_rank(user_id, include_zero=False):
    """رتبهٔ یک کاربر، یا ``None`` اگر در جدول نباشد."""
    key = accounts.user_key(user_id)
    for row in ranked_users(include_zero=include_zero):
        if row["user_id"] == key:
            return row["rank"]
    return None
