from pathlib import Path
import ast

p=Path("main.py")
s=p.read_text(encoding="utf-8")

marker='              text = (event.message.message or "").strip()\n'

block='''\n
              # RIDDLE_FINAL
              if text == "چیستان":
                  try:
                      chat_id = event.chat_id
                      sender = await event.get_sender()
                      user_id = sender.id if sender else 0

                      q = new_riddle(chat_id, user_id)

                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )
                      return

                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")

'''

if "RIDDLE_FINAL" in s:
    print("⚠️ قبلا اضافه شده")
    raise SystemExit

pos=s.find(marker)

if pos==-1:
    print("❌ محل text پیدا نشد")
    raise SystemExit

pos += len(marker)

s=s[:pos]+block+s[pos:]

try:
    ast.parse(s)
except Exception as e:
    print("❌ خطای سینتکس:",e)
    raise SystemExit

p.write_text(s,encoding="utf-8")
print("✅ چیستان نهایی اضافه شد")
