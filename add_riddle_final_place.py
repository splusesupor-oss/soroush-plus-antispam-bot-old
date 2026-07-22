from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if 'if clean_text == "چیستان":' in s:
    print("⚠️ already exists")
    exit()

target = '''              # بازی جرعت حقیقت
'''

block = '''              # RIDDLE_FINAL
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

if target not in s:
    print("❌ target not found")
    exit()

s = s.replace(target, block + target, 1)

p.write_text(s, encoding="utf-8")
print("✅ riddle added")
