#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
p="modules/admin_actions.py"

s=open(p,encoding="utf-8").read()

start=s.find("    async def ban_user")
end=s.find("    async def send_warning", start)

if start != -1 and end != -1:

    new='''    async def ban_user(self, chat_id, user_id) -> bool:
        """حذف دائمی کاربر با API سروش"""
        try:
            user = await self.client.get_entity(user_id)

            await self.client.kick_participant(
                chat_id,
                user
            )

            try:
                from modules.banned_storage import add_banned
                username = getattr(user, "username", None)
                if username:
                    add_banned(chat_id, username)
            except Exception:
                pass

            self.logger.log_action(
                "BAN",
                user_id,
                chat_id,
                "حذف دائمی به دلیل اسپم"
            )

            return True

        except Exception as e:
            self.logger.log_error(
                f"خطا در بن دائمی {user_id}: {e}"
            )
            return False

'''

    s=s[:start]+new+s[end:]

    open(p,"w",encoding="utf-8").write(s)

    print("soroush ban fixed")
else:
    print("target not found")

PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
