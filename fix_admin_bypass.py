from pathlib import Path

p = Path("test_main.py")
s = p.read_text(encoding="utf-8")

start = s.find("# ادمین‌های ثبت شده بدون هیچ فیلتری")
end = s.find("if is_spam:", start)

if start == -1 or end == -1:
    print("❌ محل بخش ادمین پیدا نشد")
    exit()

new = '''# ادمین‌های ثبت شده بدون هیچ فیلتری
admin_bypass = False

try:
    # تابع اصلی ادمین با username کار می‌کند
    admin_bypass = is_admin(chat_id, username)
    if admin_bypass:
        print(f"ADMIN BYPASS FINAL: {username}")

except Exception as e:
    print("ADMIN CHECK ERROR:", e)
    admin_bypass = False


if admin_bypass:
    is_spam = False
    reason = ""

else:
    clean_check = message_text.strip()

    if len(clean_check) <= 3 or all(not ch.isalnum() for ch in clean_check):
        is_spam = False
        reason = ""

    else:
        is_spam, reason = self.detector.is_spam(
            message_text,
            chat_id
        )


'''

s = s[:start] + new + s[end:]

p.write_text(s, encoding="utf-8")

print("✅ سیستم ادمین اصلاح شد")
