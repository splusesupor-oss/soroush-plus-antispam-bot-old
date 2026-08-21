#!/bin/bash
# راه‌اندازی ربات از طریق ناظر دائمی Watchdog.
set -u
cd "$(dirname "$0")"

echo "🤖 راه‌اندازی ربات ضد هرزنامه سروش پلاس با Watchdog..."
python3 --version

if [ ! -d "logs" ]; then
  mkdir -p logs
fi

if [ ! -f ".env" ]; then
  echo "⚠️ فایل .env یافت نشد، از .env.example کپی می‌شود"
  cp .env.example .env
  echo "لطفاً .env را ویرایش کنید و سپس دوباره اجرا کنید"
  exit 1
fi

exec python3 watchdog.py
