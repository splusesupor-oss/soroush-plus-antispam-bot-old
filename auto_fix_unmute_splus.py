from pathlib import Path
import shutil
import datetime

file = Path("handlers/message_handler.py")

backup = file.parent / (
    "message_handler.before_splus_unmute_fix_" +
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
)

shutil.copy(file, backup)

text = file.read_text(encoding="utf-8")

old = '''                  entity = await bot.client.get_input_entity(chat_id)
                  user_entity = await bot.client.get_input_entity(user)

                  await bot.client(
                      functions.channels.EditBannedRequest(
                          channel=entity,
                          participant=user_entity,
                          banned_rights=types.ChatBannedRights(
                              until_date=None
                          )
                      )
                  )'''

new = '''                  # رفع محرومیت با API سروش پلاس
                  ok = await bot.admin_actions.unban_user(
                      chat_id,
                      user.id
                  )

                  if not ok:
                      await event.reply("❌ آزادسازی توسط API انجام نشد")
                      return'''

if old in text:
    text = text.replace(old, new)
    print("✅ بخش تلگرامی آزاد حذف شد")
else:
    print("⚠️ بخش قدیمی پیدا نشد")

file.write_text(text, encoding="utf-8")

print("📌 بکاپ:", backup)
print("✅ تمام شد")
