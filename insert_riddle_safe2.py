from pathlib import Path
import shutil

p = Path("main.py")
shutil.copy2(p, "main.py.riddle_backup")

s = p.read_text(encoding="utf-8")

if "# RIDDLE_SAFE_FINAL" in s:
    print("already exists")
    exit()

pos = s.find("# بازی جرعت حقیقت")

if pos == -1:
    print("marker not found")
    exit()

pos = s.rfind("\n", 0, pos) + 1

block = '''
              # RIDDLE_SAFE_FINAL
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

s = s[:pos] + block + s[pos:]

p.write_text(s, encoding="utf-8")

print("DONE")
