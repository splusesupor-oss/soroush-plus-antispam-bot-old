from pathlib import Path
import ast, shutil, time

p=Path("main.py")
s=p.read_text(encoding="utf-8")

shutil.copy2(p, f"main.py.before_riddle_real_{int(time.time())}")

marker='              text = (event.message.message or "").strip()\n'

insert='''
              # RIDDLE_REAL
              if text == "چیستان":
                  try:
                      sender = await event.get_sender()
                      chat_id = event.chat_id
                      user_id = sender.id if sender else 0

                      q = new_riddle(chat_id, user_id)

                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

if "# RIDDLE_REAL" in s:
    print("already installed")
    raise SystemExit

pos=s.find(marker)
if pos==-1:
    print("marker not found")
    raise SystemExit

pos += len(marker)

s=s[:pos]+insert+s[pos:]

ast.parse(s)

p.write_text(s,encoding="utf-8")

print("✅ RIDDLE REAL INSTALLED")
