from pathlib import Path
import shutil

p = Path("main.py")

backup = "main.py.before_riddle_auto_timer"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

# import اصلاح شود
s = s.replace(
    "from modules.riddles import new_riddle",
    "from modules.riddles import new_riddle, check_answer, get_answer, active_riddles"
)

# بخش چیستان فعلی را پیدا و جایگزین کن
start = s.find("# RIDDLE_SAFE_INSERTED")
end = s.find("# بازی جرعت حقیقت")

if start == -1 or end == -1:
    print("❌ بخش چیستان پیدا نشد")
    exit()

new_block = '''# RIDDLE_SAFE_INSERTED
              if clean_text == "چیستان":
                  try:
                      sender = await event.get_sender()
                      user_id = getattr(sender, "id", 0)

                      chat = await event.get_chat()
                      chat_id = getattr(chat, "id", 0)

                      q = new_riddle(chat_id, user_id)

                      await event.reply(
                          "🧩 چیستان:\\n\\n" +
                          q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )

                      async def timeout_riddle():
                          await asyncio.sleep(50)

                          ans = get_answer(chat_id, user_id)

                          if ans:
                              await event.reply(
                                  "⏰ زمان تمام شد!\\n\\n"
                                  "✅ جواب چیستان: " + ans
                              )

                              active_riddles.pop(
                                  (chat_id, user_id),
                                  None
                              )

                      asyncio.create_task(timeout_riddle())

                  except Exception as e:
                      self.logger.log_error(
                          f"خطای چیستان: {e}"
                      )

                  return

'''

s = s[:start] + new_block + s[end:]

p.write_text(s, encoding="utf-8")

print("✅ ربات اصلاح شد")
print("Backup:", backup)
