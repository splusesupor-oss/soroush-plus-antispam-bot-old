#!/usr/bin/env python3
"""🪙 انتقال سکه‌های سیستم قدیمی به «سکهٔ برنز» اقتصاد جدید.

کاربرانی که پیش از راه‌اندازی اقتصاد سکه جمع کرده بودند نباید از صفر
شروع کنند. این ابزار موجودی `config/coins.json` را می‌خواند و همان
مقدار را به‌عنوان **برنز** در اقتصاد جدید ثبت می‌کند.

  • هیچ داده‌ای حذف نمی‌شود؛ `coins.json` دست‌نخورده باقی می‌ماند.
  • هر کاربر یک `reference` یکتا دارد، پس اجرای دوباره چیزی را دو بار
    اضافه نمی‌کند.
  • اگر کاربری در چند گروه سکه داشته، مجموع آن‌ها منتقل می‌شود؛ چون کیف
    پول اقتصاد جدید «به تفکیک کاربر» است نه گروه.
  • تعداد بردها (wins) هم منتقل می‌شود.

    python3 tools/migrate_legacy_coins.py --dry-run   # فقط گزارش
    python3 tools/migrate_legacy_coins.py             # اجرای واقعی
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import economy
from economy import storage
from economy.coins import accounts
from economy.transactions import ledger

LEGACY_FILE = ROOT / "config" / "coins.json"
REFERENCE = "legacy_coins_import:v1"


def read_legacy():
    """موجودی هر کاربر را از فایل قدیمی جمع می‌زند."""
    if not LEGACY_FILE.exists():
        return {}, {}, {}
    try:
        raw = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"خواندن {LEGACY_FILE} ناموفق بود: {error}")

    coins, wins, names = {}, {}, {}
    for _group, members in (raw.get("users") or {}).items():
        if not isinstance(members, dict):
            continue
        for user_id, record in members.items():
            if not isinstance(record, dict):
                continue
            coins[user_id] = coins.get(user_id, 0) + int(record.get("coins", 0) or 0)
            wins[user_id] = wins.get(user_id, 0) + int(record.get("wins", 0) or 0)
            if record.get("name"):
                names[user_id] = str(record["name"])
    return coins, wins, names


def migrate(dry_run=False):
    coins, wins, names = read_legacy()
    if not coins:
        print("هیچ موجودی قدیمی‌ای پیدا نشد؛ کاری لازم نیست.")
        return 0

    total = sum(coins.values())
    print(f"کاربران دارای سکهٔ قدیمی : {len(coins)}")
    print(f"مجموع سکه‌های قابل انتقال: {total}")
    print(f"مرجع یکتا                : {REFERENCE}")

    if dry_run:
        print("\n--- حالت آزمایشی، چیزی نوشته نمی‌شود ---")
        for user_id, amount in sorted(coins.items(), key=lambda x: -x[1])[:10]:
            current = economy.get_balance(user_id)[economy.BRONZE]
            print(f"  user {user_id:12} برنز فعلی {current:6} → +{amount}")
        return 0

    moved = skipped = 0
    # همه در یک تراکنش: یا کل انتقال ثبت می‌شود یا هیچ.
    with storage.transaction() as data:
        for user_id, amount in coins.items():
            key = accounts.user_key(user_id)
            reference = f"{REFERENCE}:{key}"
            if ledger.is_duplicate(data, key, reference):
                skipped += 1
                continue
            user = accounts._user(data, key)
            if amount > 0:
                user[accounts.BRONZE] = int(user.get(accounts.BRONZE, 0)) + amount
            if wins.get(user_id):
                user["wins"] = int(user.get("wins", 0)) + wins[user_id]
            if names.get(user_id):
                user["name"] = names[user_id]
            value = accounts._refresh_total(data, user)
            ledger.record(
                data, key, ledger.KIND_RECEIVE,
                {accounts.BRONZE: amount} if amount else {},
                reference=reference,
                note="انتقال سکه‌های سیستم قدیمی",
                balance_after=accounts._snapshot_balance(user),
                total_value=value,
            )
            moved += 1

    print(f"\n✅ منتقل شد : {moved} کاربر")
    print(f"⏭️  رد شد    : {skipped} کاربر (قبلاً منتقل شده بودند)")
    print(f"📁 فایل قدیمی دست‌نخورده باقی ماند: {LEGACY_FILE.name}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="فقط گزارش بده، چیزی ننویس")
    args = parser.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
