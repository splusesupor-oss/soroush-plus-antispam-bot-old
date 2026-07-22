#!/bin/bash

cp modules/admin_actions.py modules/admin_actions.before_kick_fix.py

python3 - <<'PY'
p="modules/admin_actions.py"

s=open(p,encoding="utf-8").read()

start=s.find("    async def ban_user")
end=s.find("    async def", start+10)

if start == -1:
    print("ban_user not found")
    exit()

if end == -1:
    end=len(s)

new='''    async def ban_user(self, chat_id, user_id) -> bool:
        """Kick + permanent storage ban"""
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
                else:
                    add_banned(chat_id, str(user_id))

            except Exception as e:
                self.logger.log_error(f"storage ban error: {e}")

            self.logger.log_action(
                "BAN",
                user_id,
                chat_id,
                "حذف دائمی به دلیل اسپم"
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در بن دائمی {user_id}: {e}")
            return False

'''

s=s[:start]+new+s[end:]

open(p,"w",encoding="utf-8").write(s)

print("ban_user replaced")
PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
