#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

# اضافه کردن import
old = "from splusthon import SoroushClient, events"
new = "from splusthon import SoroushClient, events, types\nfrom splusthon.tl import functions"

if "from splusthon.tl import functions" not in s:
    s = s.replace(old, new)

# جایگزینی آزاد قبلی
start = s.find("# آزاد کردن کاربر محروم شده از لیست")
end = s.find("# سکوت کاربر با ریپلای")

if start != -1 and end != -1:
    block = r'''# آزاد کردن کاربر محروم شده از لیست
            if clean_text == "آزاد":
                try:
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

                    entity = await self.client.get_input_entity(chat_id)
                    user_entity = await self.client.get_input_entity(user)

                    await self.client(
                        functions.channels.EditBannedRequest(
                            channel=entity,
                            participant=user_entity,
                            banned_rights=types.ChatBannedRights(
                                until_date=None
                            )
                        )
                    )

                    username = getattr(user, "username", None)

                    if username:
                        remove_banned(chat_id, username)

                    await event.reply("♻️ کاربر آزاد شد")

                except Exception as e:
                    await event.reply(f"❌ خطا در آزاد کردن:\n{e}")

                return

'''
    s = s[:start] + block + s[end:]

p.write_text(s, encoding="utf-8")
print("AZAD FIXED")
PY

python3 -m py_compile main.py && echo OK
