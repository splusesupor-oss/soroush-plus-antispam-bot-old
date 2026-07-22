from pathlib import Path

p = Path("core/bot_working_split_ok.py")
lines = p.read_text(encoding="utf-8").splitlines()

insert = [
'',
'        # آزاد کردن کاربر محروم شده',
'        if text == "آزاد":',
'            try:',
'                if not event.reply_to:',
'                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")',
'                    return',
'',
'                reply_msg = await self.client.get_messages(',
'                    event.chat_id,',
'                    ids=event.reply_to.reply_to_msg_id',
'                )',
'',
'                user = await reply_msg.get_sender()',
'                if not user:',
'                    await event.reply("❌ کاربر پیدا نشد")',
'                    return',
'',
'                await self.admin_actions.unban_user(',
'                    event.chat_id,',
'                    user.id,',
'                    getattr(user, "username", None)',
'                )',
'',
'                await event.reply("♻️ کاربر آزاد شد")',
'',
'            except Exception as e:',
'                await event.reply(f"❌ خطا در آزاد کردن: {e}")',
'            return',
''
]

for i,line in enumerate(lines):
    if 'text = (event.message.message or "").strip()' in line:
        lines[i+1:i+1] = insert
        p.write_text("\n".join(lines)+"\n", encoding="utf-8")
        print("✅ دستور آزاد اضافه شد در خط", i+1)
        break
else:
    print("❌ خط text پیدا نشد")
