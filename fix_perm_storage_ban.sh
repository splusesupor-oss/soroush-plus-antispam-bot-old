#!/data/data/com.termux/files/usr/bin/bash

cd "$(pwd)"

python3 - <<'PY'
from pathlib import Path

p=Path("modules/admin_actions.py")
s=p.read_text()

start=s.find("    async def ban_user")
end=s.find("    async def", start+10)

if start==-1:
    print("ban_user not found")
    exit()

new='''    async def ban_user(self, chat_id, user_id) -> bool:
        """Permanent ban using Soroush API"""
        try:
            user = await self.client.get_entity(user_id)

            # remove user
            await self.client.kick_participant(
                chat_id,
                user
            )

            # permanent storage ban
            try:
                from modules.banned_storage import add_banned
                username = getattr(user, "username", None)

                if username:
                    add_banned(chat_id, username)
                else:
                    add_banned(chat_id, str(user_id))

            except Exception as e:
                self.logger.error(f"storage ban error: {e}")

            self.logger.log_action(
                "BAN",
                user_id,
                chat_id,
                "حذف دائمی به دلیل اسپم"
            )

            return True

        except Exception as e:
            self.logger.error(f"خطا در بن دائمی {user_id}: {e}")
            return False

'''

p.write_text(s[:start]+new+s[end:])

print("ban_user fixed")
PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
