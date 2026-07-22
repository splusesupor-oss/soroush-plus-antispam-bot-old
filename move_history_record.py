from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

old = "            add_message(chat_id, user_id, event.message.id, message_text)"

# حذف ثبت فعلی
s = s.replace(old, "")

# جای مناسب: قبل از بررسی فیلتر اسپم
target = "        # بررسی اسپم"

if target in s and "add_message(chat_id, user_id, event.message.id, message_text)" not in s:
    s = s.replace(
        target,
        "        # ذخیره تاریخچه پیام برای تشخیص تکرار\n"
        "        try:\n"
        "            add_message(chat_id, user_id, event.message.id, message_text)\n"
        "        except Exception as e:\n"
        "            print('history save error:', e)\n\n"
        + target,
        1
    )

p.write_text(s, encoding="utf-8")
print("✅ history moved before spam filter")
