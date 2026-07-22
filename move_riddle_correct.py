from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

block = '''              # RIDDLE_SAFE_INSERTED
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

if block not in s:
    print("❌ riddle block not found")
    exit()

s = s.replace(block, "", 1)

target = '''                  chat_id = getattr(chat, "id", 0)
'''

insert = '''
              
              # RIDDLE_SAFE_INSERTED
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

s = s.replace(target, target + insert, 1)

p.write_text(s, encoding="utf-8")
print("✅ riddle moved correctly")
