#!/bin/bash
# اجرای ربات با restart خودکار در صورت خطا

echo "🤖 راه‌اندازی ربات ضد هرزنامه سروش پلاس..."

# چک python
python3 --version

# نصب نیازمندی‌ها اگر نصب نیست
if [ ! -d "logs" ]; then
  mkdir -p logs
fi

if [ ! -f ".env" ]; then
  echo "⚠️ فایل .env یافت نشد، از .env.example کپی می‌شود"
  cp .env.example .env
  echo "لطفا .env را ویرایش کنید سپس دوباره اجرا کنید"
  exit 1
fi

# حلقه اجرای خودکار
while true; do
  echo "🚀 اجرای main.py در $(date)"
  python3 main.py
  echo "⚠️ ربات متوقف شد، 5 ثانیه دیگر دوباره تلاش می‌شود... (Ctrl+C برای خروج)"
  sleep 5
done
