#!/data/data/com.termux/files/usr/bin/bash
# ورودی دائمی ربات: Watchdog مالک اجرای main.py و restartها است.
set -u
cd "$(dirname "$0")"
exec python3 watchdog.py
