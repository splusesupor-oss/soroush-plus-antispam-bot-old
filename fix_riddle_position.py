from pathlib import Path
import shutil

p=Path("main.py")
s=p.read_text(encoding="utf-8")

shutil.copy2(p,"main.py.before_riddle_position")

start=s.find("        # RIDDLE_AUTO")
if start!=-1:
    end=s.find("\n", s.find("return", start))+1
    s=s[:start]+s[end:]

marker='        text = (event.message.message or "").strip()'

block='''
        # RIDDLE_AUTO
        if text == "چیستان":
            try:
                q = new_riddle(chat_id, user_id)
                await event.reply(
                    "🧩 چیستان:\\n\\n" + q +
                    "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                )
                return
            except Exception as e:
                self.logger.log_error(f"خطای چیستان: {e}")
'''

pos=s.find(marker)
if pos!=-1:
    pos=s.find("\n",pos)+1
    s=s[:pos]+block+s[pos:]
else:
    print("❌ text marker not found")

p.write_text(s,encoding="utf-8")
print("✅ جای چیستان اصلاح شد")
