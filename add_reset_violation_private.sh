#!/bin/bash

python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

marker='            # فعال و غیرفعال کردن گروه توسط مالک اصلی'

code='''
            # صفر کردن تخلفات کاربر با ریپلای
            if clean_text == "صفر":
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

                    self.tracker.reset_count(chat_id, user.id)

                    await event.reply("✅ تخلفات کاربر صفر شد")

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return

'''

if marker in s:
    s=s.replace(marker,code+marker)
    open(p,"w",encoding="utf-8").write(s)
    print("reset violation added")
else:
    print("marker not found")
PY

python3 -m py_compile main.py && echo "syntax ok"
