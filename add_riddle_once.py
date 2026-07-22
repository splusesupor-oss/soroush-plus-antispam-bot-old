from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

target = '              if clean_text in ["جرعت", "جرات", "جرئت"]:\n'

insert = '''              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

if "if clean_text == \"چیستان\":" in s:
    print("already exists")
elif target in s:
    s = s.replace(target, insert + target, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ inserted")
else:
    print("❌ target not found")
