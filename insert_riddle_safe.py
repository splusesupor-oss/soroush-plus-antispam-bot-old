from pathlib import Path
import shutil

p = Path("main.py")
backup = Path("main.py.before_riddle_safe_final")

shutil.copy2(p, backup)

s = p.read_text(encoding="utf-8")

# اگر قبلاً اضافه شده بود
if "# RIDDLE_SAFE_FINAL" in s:
    print("⚠️ already inserted")
    exit()

marker = '''              # بازی جرعت حقیقت
'''

if marker not in s:
    print("❌ marker not found")
    exit()

block = '''              # RIDDLE_SAFE_FINAL
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

s = s.replace(marker, block + marker, 1)

p.write_text(s, encoding="utf-8")

print("✅ riddle inserted safely")
print("backup:", backup)
