#!/data/data/com.termux/files/usr/bin/bash
# توقف ناظر قبلی و اجرای یک Watchdog جدید.
set -u
cd "$(dirname "$0")"

pkill -f '[p]ython3 .*watchdog.py' 2>/dev/null || true
pkill -f '[p]ython3 .*main.py' 2>/dev/null || true
sleep 2
exec python3 watchdog.py
