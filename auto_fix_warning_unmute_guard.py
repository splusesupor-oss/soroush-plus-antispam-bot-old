from pathlib import Path
import shutil
import datetime

file=Path("handlers/message_handler.py")

backup=file.with_name(
    "message_handler.before_warning_unmute_guard_fix_"+
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(file, backup)

text=file.read_text(encoding="utf-8")


def add_guard(text, command):

    patterns=[
        f'if clean_text == "{command}"',
        f'if clean_text.startswith("{command}")'
    ]

    for p in patterns:
        idx=text.find(p)

        if idx!=-1:

            line_start=text.rfind("\n",0,idx)+1

            indent=text[line_start:idx]

            block=text[idx:idx+600]

            if "is_admin(" in block:
                print("⏭ قبلا محافظ دارد:",command)
                return text

            guard=(
                "\n"
                + indent +
                "sender_username = getattr(sender, \"username\", None)\n"
                + indent +
                "if not is_admin(chat_id, sender_username):\n"
                + indent +
                "    await event.reply(\"❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند\")\n"
                + indent +
                "    return\n"
            )

            insert_pos=idx+len(p)

            text=text[:insert_pos]+guard+text[insert_pos:]

            print("✅ محافظ اضافه شد:",command)
            return text

    print("❌ پیدا نشد:",command)
    return text


text=add_guard(text,"اخطار")
text=add_guard(text,"رفع سکوت")


file.write_text(text,encoding="utf-8")

print("📌 بکاپ:",backup)
print("✅ تمام شد")

