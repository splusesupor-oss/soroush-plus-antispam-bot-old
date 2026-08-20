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

## مهاجرت امن داده‌های Termux به حافظهٔ داخلی

### چرا این مرحله ضروری است؟

SQLite، فایل‌های موقت، `fsync` و لاگ پرترافیک روی حافظهٔ اشتراکی اندروید
(`/storage/emulated/0` یا `/sdcard`) کند و نامطمئن‌ترند. سورس پروژه می‌تواند
همان‌جا بماند، ولی دادهٔ در حال تغییر باید داخل home خصوصی Termux باشد.
مسیر پیش‌فرض ربات روی Termux این است:

```text
/data/data/com.termux/files/home/.local/share/soroush-bot
```

می‌توانید با `SOROUSH_BOT_DATA_DIR` مسیر دیگری **داخل home خصوصی Termux** بدهید.

### مراحل دقیق مهاجرت

1. ربات را متوقف کنید و مطمئن شوید پردازش دیگری از آن باز نیست:

```bash
pkill -f 'python.*main.py' 2>/dev/null || true
```

2. از وضعیت فعلی پروژه یک کپی rollback داخل home خصوصی بسازید. دستور زیر
فایل مبدأ را حذف نمی‌کند:

```bash
cd /storage/emulated/0/Download/soroush-plus-antispam-bot-old
stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$HOME/soroush-pre-migration-$stamp"
cp -a config "$HOME/soroush-pre-migration-$stamp/"
cp -a logs "$HOME/soroush-pre-migration-$stamp/" 2>/dev/null || true
```

3. مسیر runtime را بسازید و در shell دائمی کنید. این خط باید **قبل از
`python main.py`** اعمال شده باشد:

```bash
mkdir -p "$HOME/.local/share/soroush-bot"
chmod 700 "$HOME/.local/share/soroush-bot"
grep -q SOROUSH_BOT_DATA_DIR "$HOME/.profile" || \
  printf '\nexport SOROUSH_BOT_DATA_DIR="$HOME/.local/share/soroush-bot"\n' >> "$HOME/.profile"
. "$HOME/.profile"
printf '%s\n' "$SOROUSH_BOT_DATA_DIR"
```

4. ربات را یک بار عادی اجرا کنید:

```bash
python main.py
```

در اولین راه‌اندازی، مهاجرت خودکار این رفتار را دارد:

- فایل‌های قدیمی **کپی** می‌شوند، نه move؛ مبدأ برای rollback باقی می‌ماند.
- کپی با SHA-256، `fsync` و replace اتمیک تأیید می‌شود.
- `config/coins.json` قدیمی مستقیماً به کیف پول‌های گروهی SQLite تبدیل می‌شود؛
  موجودی، بردها، نام‌ها، شمارش روزانه و روزهای تسویه‌شده حفظ می‌شوند.
- اگر `config/economy.json` وجود داشته باشد، همان منبع جدیدتر اولویت دارد.
- بن‌های دائمی، aliasها، `user_activity.json`، لاگ مدیریتی و پیشرفت چیستان/پرچم
  به جدول‌های ایندکس‌شده منتقل می‌شوند.
- فایل‌های JSON مبدأ حذف نمی‌شوند و یک بکاپ قبل از مهاجرت در `backups/`
  ساخته و بررسی می‌شود.
- SQLite با WAL، `synchronous=FULL`، تراکنش و integrity check اجرا می‌شود.

> `config/config.json` و `.env` عمداً deployment-local باقی می‌مانند. مقادیر
> session، رمز یا token را داخل log، Git یا پیام عمومی قرار ندهید.

### بررسی نتیجه

ربات هنگام شروع باید خط `RUNTIME STORAGE READY` با integrity برابر `ok` چاپ
کند. برای بررسی مستقل، پس از توقف ربات دستور زیر را اجرا کنید:

```bash
python - <<'PY'
from modules.runtime_paths import describe
from modules import runtime_db
from economy import storage
print(describe())
print("economy_backend=", storage.backend_name())
print("economy_integrity=", storage.integrity_check())
print("runtime_integrity=", runtime_db.integrity_check())
print("runtime_stats=", runtime_db.stats())
assert storage.integrity_check() == "ok"
assert runtime_db.integrity_check() == "ok"
PY
```

مقادیر صحیح در Termux:

- `private: True`
- `economy_backend: sqlite`
- فایل DB زیر `$SOROUSH_BOT_DATA_DIR/db/bot.sqlite3`
- هر دو integrity برابر `ok`

### بکاپ و نگهداری خودکار

در شروع و سپس روزانه، maintenance خارج از event loop اجرا می‌شود: integrity
check، حذف state منقضی، checkpoint/optimize و بکاپ آنلاینِ تأییدشده. حداکثر
۱۴ بکاپ عادی `bot-*.sqlite3` نگه داشته می‌شود؛ بکاپ‌های قبل از مهاجرت با
پیشوندهای دیگر خودکار پاک نمی‌شوند.

متغیرهای اختیاری:

```bash
export BOT_BACKUP_KEEP=14
export BOT_BACKUP_INTERVAL_SECONDS=86400
export BOT_ACTIVITY_RETENTION_DAYS=180
export BOT_ECONOMY_ARCHIVE_DAYS=365
export BOT_LOG_MAX_BYTES=20971520
export BOT_LOG_BACKUPS=5
```

### rollback به JSON بدون از دست دادن تغییرات جدید

ابتدا ربات را متوقف کنید. سپس در حالی که backend هنوز SQLite است، از state
فعلی JSON تأییدشده بسازید:

```bash
python - <<'PY'
# Import این دو ماژول، storeهای پیشرفت را ثبت می‌کند.
from modules import riddles, flag_guess
from economy import storage
from modules import banned_storage, user_activity
from modules.game_progress_storage import export_all_json
from modules.admin_tools import export_admin_log_json
print(storage.export_json())
print(banned_storage.export_json())
print(user_activity.export_json())
print(export_all_json())
print(export_admin_log_json())
PY
```

بعد این دو متغیر را به محیط اجرای ربات اضافه کنید و ربات را روشن کنید:

```bash
export ECONOMY_BACKEND=json
export RUNTIME_STATE_BACKEND=json
python main.py
```

مسیر خصوصی را تغییر ندهید؛ JSONهای export‌شده در همان
`$SOROUSH_BOT_DATA_DIR/config` هستند. برای برگشت به SQLite، دو override بالا
را حذف کنید.

### بازگردانی یک بکاپ SQLite

```bash
pkill -f 'python.*main.py' 2>/dev/null || true
cd "$SOROUSH_BOT_DATA_DIR"
cp -a db/bot.sqlite3 "db/bot.sqlite3.failed-$(date +%Y%m%d-%H%M%S)"
rm -f db/bot.sqlite3-wal db/bot.sqlite3-shm
cp -a backups/bot-YYYYMMDD-HHMMSS.sqlite3 db/bot.sqlite3
chmod 600 db/bot.sqlite3
python main.py
```

نام واقعی بکاپ را به جای `bot-YYYYMMDD-HHMMSS.sqlite3` بگذارید. پیش از
جایگزینی DB، ربات حتماً باید متوقف باشد.

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
