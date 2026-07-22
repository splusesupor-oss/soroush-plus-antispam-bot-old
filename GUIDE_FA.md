# راهنمای فارسی نصب قدم به قدم

## چرا دو حالت داریم؟

سروش پلاس دو نوع ربات دارد:

1. **User-Bot با SPlusthon** (پیشنهادی شما):
   - ربات روی حساب شخصی شما اجرا می‌شود
   - می‌تواند پیام حذف کند، کاربر را سایلنت و بن کند
   - دقیقاً همان چیزی که شما خواستید
   - کتابخانه: SPlusthon (فورک Telethon)

2. **Bot API رسمی**:
   - ربات رسمی که از @MrBot می‌سازید
   - محدودیت بیشتر
   - فقط برای اطلاع‌رسانی خوب است

ما هر دو را پیاده کردیم، ولی **main.py برای شماست**.

---

## نصب سریع (3 دقیقه)

### مرحله 1: نصب کتابخانه‌ها

```bash
pip install splusthon python-dotenv requests sseclient-py colorama
```

یا:

```bash
pip install -r requirements.txt
```

### مرحله 2: دریافت Session

```bash
python get_session.py
```

شماره سروش خود را وارد کنید: `+98...`
کد تایید را وارد کنید.

یک رشته طولانی به شما می‌دهد مثل `1Aaaa...`. آن را کپی کنید.

### مرحله 3: تنظیم .env

```bash
cp .env.example .env
nano .env
```

داخلش بنویسید:

```
SOROUSH_SESSION_STRING=رشته_ای_که_گرفتید
```

### مرحله 4: تنظیم ادمین‌ها

در `config/config.json`:

```json
"admin_user_ids": [123456789],
"whitelisted_user_ids": [123456789]
```

به جای 123456789، آیدی عددی خودتان را بگذارید. بعد از اولین اجرا در ترمینال آیدی شما چاپ می‌شود.

### مرحله 5: تنظیم کلمات ممنوعه

`config/banned_words.txt` را ویرایش کنید، هر خط یک کلمه.

### مرحله 6: اجرا

```bash
python main.py
```

حالا هر گروهی که شما در آن باشید، ربات پیام‌ها را چک می‌کند.

برای اینکه فقط گروه خاصی را چک کند، در config.json:

```json
"target_groups": [-100123456789]
```

---

## تست بدون سروش

```bash
python test_detector.py
```

خروجی نشان می‌دهد کدام پیام اسپم تشخیص داده می‌شود.

---

## مجازات چطور کار می‌کند؟

در `tracker.py` برای هر گروه و هر کاربر یک شمارنده داریم.

- بار اول اسپم: حذف + هشدار
- بار دوم: حذف + هشدار
- بار سوم (یا آستانه تنظیم شده): حذف + هشدار + mute/ban

در config:

```json
"spam_threshold": 3,
"action_on_threshold": "mute",
"action_duration_seconds": 3600
```

اگر `mute` باشد: کاربر به مدت 1 ساعت نمی‌تواند پیام بفرستد.
اگر `ban` باشد: از گروه حذف می‌شود.

---

## دستورات داخل گروه

فقط کسانی که در `admin_user_ids` هستند می‌توانند استفاده کنند:

```
!addword کلمه
!stats
!help
```

---

## اجرای 24 ساعته روی سرور

### روش screen:

```bash
screen -S soroush
python main.py
# Ctrl+A سپس D برای خروج از screen
```

### روش nohup:

```bash
nohup python main.py > logs/bot.log 2>&1 &
```

### روش systemd (حرفه‌ای):

فایل `/etc/systemd/system/soroush-bot.service` بسازید:

```
[Unit]
Description=Soroush AntiSpam Bot
After=network.target

[Service]
WorkingDirectory=/root/soroush-plus-antispam-bot
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

سپس:

```bash
systemctl enable soroush-bot
systemctl start soroush-bot
```

---

## عیب‌یابی

| مشکل | راه حل |
|------|--------|
| `ChatAdminRequiredError` | حساب شما در گروه ادمین نیست یا دسترسی حذف پیام ندارد |
| پیام حذف نمی‌شود | چک کنید ربات ادمین است و `delete_spam=true` |
| کلمات جدید اعمال نمی‌شود | `enable_hot_reload_banned_words=true` است، هر پیام تنظیمات را ریلود می‌کند |
| شماره اشتباه تشخیص داده می‌شود | الگوی شماره را در `spam_detector.py` سختگیرانه‌تر کنید |

---

موفق باشید!
