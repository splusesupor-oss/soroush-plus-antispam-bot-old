python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

old="""    async def is_admin_user(self, event, user_id):
        try:
            return is_admin(user_id)
        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False
"""

new="""    async def is_admin_user(self, event, user_id):
        try:
            sender = await event.get_sender()
            username = getattr(sender, "username", None)

            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None)

            return is_admin(chat_id, username)

        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False
"""

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("ADMIN ARGS FIX OK")
PY

python3 -m py_compile main.py && echo "MAIN OK"
