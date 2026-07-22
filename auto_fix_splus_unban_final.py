from pathlib import Path
import shutil,datetime,re

p=Path("handlers/message_handler.py")

backup=p.with_name(
    "message_handler.before_splus_unban_final_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

start=text.find("# آزاد کردن کاربر محروم شده از لیست")
end=text.find("#",start+10)

if start==-1:
    print("❌ بخش آزاد پیدا نشد")
    exit()

block=text[start:end]

new_block='''# آزاد کردن کاربر محروم شده
        if clean_text == "آزاد":
            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                ok = await bot.admin_actions.unban(
                    chat_id,
                    user.id
                )

                if ok:
                    username = getattr(user,"username",None)
                    if username:
                        remove_banned(chat_id, username)

                    await event.reply("♻️ کاربر آزاد شد ✅")
                else:
                    await event.reply("❌ آزاد کردن انجام نشد")

            except Exception as e:
                await event.reply(f"❌ خطا در آزاد کردن:\\n{e}")

            return

'''

text=text[:start]+new_block+text[end:]

p.write_text(text,encoding="utf-8")

print("✅ آزاد کردن با API سروش پلاس جایگزین شد")
print("📌 بکاپ:",backup)
