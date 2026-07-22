from pathlib import Path
import shutil
import datetime

current = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.before_warning_unmute_guard_fix_20260720_130402.py")

if not backup.exists():
    print("❌ بکاپ پیدا نشد")
    exit()

shutil.copy(backup, current)

print("✅ برگشت از بکاپ انجام شد")

text = current.read_text(encoding="utf-8")


def fix(text, command):

    marker = f'if clean_text == "{command}"'

    idx = text.find(marker)

    if idx == -1:
        print("❌ پیدا نشد:", command)
        return text

    # اگر قبلا : حذف شده باشد درستش کن
    end = idx + len(marker)

    if text[end:end+1] != ":":
        text = text[:end] + ":" + text[end:]

    line_start = text.rfind("\n", 0, idx) + 1
    indent = text[line_start:idx]

    guard = (
        "\n"
        + indent + "    sender_username = getattr(sender, \"username\", None)\n"
        + indent + "    if not is_admin(chat_id, sender_username):\n"
        + indent + "        await event.reply(\"❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند\")\n"
        + indent + "        return\n"
    )

    insert_pos = end + 1

    text = text[:insert_pos] + guard + text[insert_pos:]

    print("✅ محافظ اضافه شد:", command)

    return text


text = fix(text, "اخطار")
text = fix(text, "رفع سکوت")

current.write_text(text, encoding="utf-8")

print("✅ ذخیره شد")

