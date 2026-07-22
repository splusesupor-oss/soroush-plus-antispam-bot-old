from pathlib import Path
import shutil

p = Path("main.py")
shutil.copy2(p, "main.py.before_riddle_final_safe")

s = p.read_text(encoding="utf-8")

start = s.find("# RIDDLE_SAFE_INSERTED")

if start == -1:
    print("❌ riddle block not found")
    exit()

end = s.find("# ثبت آمار پیام گروه", start)

if end == -1:
    print("❌ end not found")
    exit()

block = s[start:end]

# حذف چیستان قدیمی
s = s[:start] + s[end:]

# پیدا کردن پایان try فیلتر کلمات
marker = '                  )\n\n              except Exception as e:\n                  self.logger.log_error(\n                      f"خطای فیلتر گروه: {e}"\n                  )'

pos = s.find(marker)

if pos == -1:
    print("❌ filter block not found")
    exit()

pos += len(marker)

new_block = """

              # RIDDLE_SAFE_FINAL
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

"""

s = s[:pos] + new_block + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ moved")
