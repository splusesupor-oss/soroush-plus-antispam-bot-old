from pathlib import Path
import shutil

p=Path("main.py")
s=p.read_text(encoding="utf-8")

shutil.copy2(p,"main.py.before_riddle_restore")

# import
if "from modules.riddles import" not in s:
    lines=s.splitlines()
    lines.insert(10,"from modules.riddles import new_riddle, check_answer")
    s="\n".join(lines)+"\n"

# محل بعد از clean_text
marker='text = (event.message.message or "").strip()'

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

if "# RIDDLE_AUTO" not in s:
    pos=s.find(marker)
    if pos!=-1:
        end=s.find("\n",pos)+1
        s=s[:end]+block+s[end:]
    else:
        print("❌ marker پیدا نشد")

p.write_text(s,encoding="utf-8")
print("✅ چیستان وصل شد")
print("📦 بکاپ: main.py.before_riddle_restore")
