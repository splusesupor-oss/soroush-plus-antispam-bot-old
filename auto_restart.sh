#!/data/data/com.termux/files/usr/bin/bash
# نام قدیمی برای سازگاری؛ حلقه restart فقط در watchdog.py قرار دارد.
set -u
cd "$(dirname "$0")"
exec python3 watchdog.py
