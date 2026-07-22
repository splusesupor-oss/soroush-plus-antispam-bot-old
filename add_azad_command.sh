#!/data/data/com.termux/files/usr/bin/bash

FILE="main.py"

cp "$FILE" "${FILE}.before_azad_$(date +%s)"

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if 'if clean_text == "آزاد":' in s:
    print("AZAD already exists")
    raise SystemExit

marker = '# سکوت کاربر با ریپلای'

code = r'''
# آزاد کردن کاربر محروم شده از لیست
            if clean_text == "آزاد":
                try:
                    sender = await event.get_sender()
                    sender_username = getattr(sender, "username", None)

                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه آزاد کردن دارند")
                        return

                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    user = await reply_msg.get_sender()

                    if not user:
                        await event.reply("❌ کاربر پیدا نشد")
                        return

                    username = getattr(user, "username", None)

                    if not username:
                        await event.reply("❌ کاربر یوزرنیم ندارد")
                        return

                    if remove_banned(chat_id, username):
                        await event.reply(
                            f"♻️ کاربر @{username} از لیست محروم‌ها حذف شد"
                        )
                    else:
                        await event.reply(
                            "❌ این کاربر در لیست محروم‌ها نیست"
                        )

                except Exception as e:
                    await event.reply(f"❌ خطا در آزاد کردن:\n{e}")

                return

'''

if marker not in s:
    print("MARKER NOT FOUND")
    raise SystemExit(1)

s = s.replace(marker, code + marker)

p.write_text(s, encoding="utf-8")
print("AZAD ADDED")
PY

python3 -m py_compile main.py

if [ $? -eq 0 ]; then
    echo "OK"
else
    echo "ERROR - restore backup"
fi
