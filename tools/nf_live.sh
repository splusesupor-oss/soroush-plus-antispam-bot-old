#!/usr/bin/env bash
# 🔎 یک پیام از کاربر مشکوک بفرست، بعد این را بزن.
# خروجی دقیقاً می‌گوید ربات چه نام نمایشی‌ای دیده و چرا اقدام نکرده.
cd "$(dirname "$0")/.." || exit 1
echo "=== کامیت در حال اجرا ==="
git rev-parse --short HEAD
echo
echo "=== آیا کد جدید روی دیسک است؟ ==="
grep -c "NAME FILTER CHECK" handlers/message_handler.py
echo
echo "=== ۴۰ خط آخر بررسی نام ==="
grep -rhoE "NAME FILTER (CHECK|HIT|MATCH FAILED).*" logs/ 2>/dev/null | tail -40
echo
echo "=== اقدامات انجام‌شده ==="
grep -rhoE "AD NAME (MESSAGE DELETE QUEUED|BAN QUEUED|BAN FINISHED|BAN FAILED).*" logs/ 2>/dev/null | tail -20
