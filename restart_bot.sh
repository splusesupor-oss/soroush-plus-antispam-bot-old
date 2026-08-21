#!/data/data/com.termux/files/usr/bin/bash
# توقف کامل ناظر قبلی و اجرای یک Watchdog جدید.
set -u
cd "$(dirname "$0")"

# ابتدا خود Watchdog را متوقف می‌کنیم؛ او child مربوط به main.py را هم با
# SIGTERM می‌بندد و قفل کرنلی را آزاد می‌کند. وجود فایل watchdog.lock به‌تنهایی
# به معنی اجرای ناظر نیست و نیازی به حذف دستی آن وجود ندارد.
pkill -TERM -f '[w]atchdog\.py' 2>/dev/null || true

# به‌جای sleep ثابت، تا آزادشدن واقعی پردازش قبلی صبر کن. این کار جلوی race
# میان shutdown ناظر قدیمی و acquire ناظر جدید را می‌گیرد.
for _attempt in $(seq 1 30); do
    if ! pgrep -f '[w]atchdog\.py' >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# فقط اگر نمونه قبلی پس از ۱۵ ثانیه هنوز زنده است، آن را اجباری ببند.
if pgrep -f '[w]atchdog\.py' >/dev/null 2>&1; then
    pkill -KILL -f '[w]atchdog\.py' 2>/dev/null || true
    sleep 0.5
fi

# سازگاری با اجراهای قدیمی که main.py را بدون Watchdog بالا آورده‌اند.
pkill -TERM -f '[p]ython(3)? .*main\.py' 2>/dev/null || true
sleep 0.5

exec python3 watchdog.py
