python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

old='''        if not text.startswith(("!", "/", ".")):
            return

        cmd_text = text[1:].strip()'''

new='''        if text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
            if not await self.is_admin_user(event, admin_id):
                await event.respond("❌ فقط مدیر می‌تواند این دستور را اجرا کند")
                return

            if text == "لغو کلمات ممنوعه":
                disable(chat_id)
                await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")
                return

            if text == "فعال کلمات ممنوعه":
                enable(chat_id)
                await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")
                return

        if not text.startswith(("!", "/", ".")):
            return

        cmd_text = text[1:].strip()'''

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("ADMIN PLAIN ORDER FIX OK")
PY

python3 -m py_compile main.py && echo "MAIN OK"
