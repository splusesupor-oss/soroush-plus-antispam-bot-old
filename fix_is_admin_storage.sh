python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

if "from modules.admin_storage import is_admin, add_admin, remove_admin" not in s:
    s="from modules.admin_storage import is_admin, add_admin, remove_admin\n"+s

old="""    async def is_admin_user(self, event, user_id):
        try:
            sender = await event.get_sender()
            return self.config_manager.is_admin(user_id)
        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False
"""

new="""    async def is_admin_user(self, event, user_id):
        try:
            return is_admin(user_id)
        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False
"""

if old not in s:
    print("OLD FUNCTION NOT FOUND")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("ADMIN STORAGE CHECK FIX OK")
PY

python3 -m py_compile main.py && echo "MAIN OK"
