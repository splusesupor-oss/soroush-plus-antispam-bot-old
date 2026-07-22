from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_riddle_reorder"
shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

riddle = '''            # RIDDLE_MOVED_BEFORE_FILTER
            if clean_text == "چیستان":
                try:
                    q = new_riddle(chat_id, user_id)
                    await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                    asyncio.create_task(self.riddle_timeout_reply(event, chat_id, user_id))
                except Exception as e:
                    self.logger.log_error(f"خطای چیستان: {e}")
                return

'''

start = s.find("            # RIDDLE_SAFE_INSERTED")
end = s.find("            # بازی جرعت حقیقت")

if start == -1:
    print("riddle block not found")
    exit()

old = s[start:end]
s = s.replace(old, "")

pos = s.find("            # اتصال دستورات فیلتر کلمات گروه")

if pos == -1:
    print("filter point not found")
    exit()

s = s[:pos] + riddle + s[pos:]

p.write_text(s, encoding="utf-8")
print("DONE backup:", backup)
