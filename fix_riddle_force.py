from pathlib import Path
import shutil,time,ast

p=Path("main.py")
backup=Path(f"main.py.before_riddle_force_{int(time.time())}")

print("🧩 RIDDLE FORCE FIX")

s=p.read_text(encoding="utf-8")
shutil.copy2(p,backup)
print("📦",backup)

# حذف هر چیستان قبلی خراب
marks=[
    "# RIDDLE_AUTO",
    "# RIDDLE_SAFE",
    "if text == \"چیستان\":",
    "if clean_text == \"چیستان\":"
]

for m in marks:
    while True:
        a=s.find(m)
        if a==-1:
            break
        b=s.find("                # پیوی فقط دستور صفر کردن تخلف",a)
        if b==-1:
            b=a+300
        s=s[:a]+s[b:]
        print("🧹 removed old:",m)

# پیدا کردن هندلر پیام
pos=s.find("async def new_message_handler(event):")

if pos==-1:
    print("❌ handler پیدا نشد")
    raise SystemExit

# پیدا کردن بعد از text
insert=s.find("text = (event.message.message or \"\").strip()",pos)

if insert==-1:
    print("❌ محل text پیدا نشد")
    raise SystemExit

end=s.find("\n",insert)+1

block='''
        # RIDDLE_FORCE
        if text == "چیستان":
            try:
                chat_id = event.chat_id
                sender = await event.get_sender()
                user_id = sender.id if sender else 0

                q = new_riddle(chat_id,user_id)

                await event.reply(
                    "🧩 چیستان:\\n\\n" + q +
                    "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                )
                return

            except Exception as e:
                self.logger.log_error(f"خطای چیستان: {e}")

'''

s=s[:end]+block+s[end:]

try:
    ast.parse(s)
except Exception as e:
    print("❌ syntax fail:",e)
    shutil.copy2(backup,p)
    raise SystemExit

p.write_text(s,encoding="utf-8")

print("✅ RIDDLE FORCE INSTALLED")
