from pathlib import Path
import shutil
import datetime

file = Path("handlers/message_handler.py")

backup = Path(
    "handlers/message_handler.before_remaining_admin_guard_" +
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S") +
    ".py"
)

shutil.copy(file, backup)

text = file.read_text(encoding="utf-8")


def add_guard(text, patterns):

    for pattern, name in patterns:

        idx = text.find(pattern)

        if idx == -1:
            print("❌ پیدا نشد:", name)
            continue

        # اگر قبلا محافظ نزدیکش هست رد کن
        around = text[idx:idx+300]

        if "if not is_admin" in around or "فقط ادمین" in around:
            print("✅ قبلا محافظ دارد:", name)
            continue

        line_start = text.rfind("\n",0,idx)+1
        indent = text[line_start:idx]

        guard = (
            "\n"
            + indent + "    sender_username = getattr(sender, \"username\", None)\n"
            + indent + "    if not is_admin(chat_id, sender_username):\n"
            + indent + "        await event.reply(\"❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند\")\n"
            + indent + "        return\n"
        )

        end = idx + len(pattern)

        if text[end:end+1] != ":":
            text = text[:end] + ":" + text[end:]

        text = text[:end+1] + guard + text[end+1:]

        print("✅ محافظ اضافه شد:", name)

    return text


patterns = [

('if clean_text.startswith("ثبت ادمین")',
'ثبت ادمین'),

('if clean_text.startswith("برکناری ادمین")',
'برکناری ادمین'),

('if clean_text == "سکوت"',
'سکوت'),

('if clean_text == "رفع سکوت"',
'رفع سکوت'),

('if clean_text == "اخراج"',
'اخراج'),

('if clean_text == "پاک"',
'پاک'),

]


text = add_guard(text, patterns)

file.write_text(text,encoding="utf-8")

print("📌 بکاپ:",backup)
print("✅ تمام شد")

