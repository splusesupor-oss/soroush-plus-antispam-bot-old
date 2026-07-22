from pathlib import Path

print("🔎 بررسی مسیر حذف و اخطار\n")

main = Path("main.py").read_text(encoding="utf-8")

checks = [
    "is_spam, reason = self.detector.is_spam",
    "delete_message",
    "send_warning",
    "punish_user",
    "tracker.increment",
    "should_punish"
]

for c in checks:
    if c in main:
        print("✅ پیدا شد:", c)
    else:
        print("❌ نیست:", c)

print("\n🔎 بررسی event پیام")

if "NewMessage" in main:
    print("✅ هندلر پیام وجود دارد")
else:
    print("❌ هندلر پیام پیدا نشد")

print("\n🔎 بررسی اجرا شدن تابع اصلی")

pos = main.find("is_spam, reason")
if pos != -1:
    print("✅ بخش تشخیص در خط تقریبی:", main[:pos].count("\n")+1)
else:
    print("❌ بخش تشخیص پیدا نشد")

