#!/usr/bin/env bash
# 🔎 عیب‌یابی زندهٔ فیلتر اسم.
#   ۱) در گروه بنویس: فیلتر اسم حسین
#   ۲) بعد با همان کاربر یک پیام بفرست
#   ۳) این را بزن:  bash tools/nf_live.sh
cd "$(dirname "$0")/.." || exit 1

echo "=== کامیت ==="
git rev-parse --short HEAD

echo
echo "=== فایل فیلترها ==="
python3 - <<'PY'
from modules import name_filters
from pathlib import Path
print("path:", name_filters.FILE)
p = Path(name_filters.FILE)
print(p.read_text(encoding="utf-8") if p.exists() else "<<فایل وجود ندارد — هیچ فیلتری ذخیره نشده>>")
PY

echo
echo "=== ثبت/حذف/لیست (storage_key را با CHECK مقایسه کن) ==="
grep -rhoE "NAME FILTER (ADDED|REMOVED|LIST|DENIED|ADD REJECTED|REMOVE REJECTED).*" logs/ 2>/dev/null | tail -20

echo
echo "=== بررسی نام در پیام‌های گروه ==="
grep -rhoE "NAME FILTER (CHECK|HIT|MATCH FAILED).*" logs/ 2>/dev/null | tail -25

echo
echo "=== اقدامات ==="
grep -rhoE "AD NAME (MESSAGE DELETE QUEUED|BAN QUEUED|BAN FINISHED|BAN FAILED).*" logs/ 2>/dev/null | tail -15
