#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

start = s.find("    async def mute_user(")
end = s.find("    async def unmute_user(", start)

if start == -1 or end == -1:
    print("❌ mute_user پیدا نشد")
    exit()

new_func = '''    async def mute_user(self, chat_id, user_id, duration_seconds=3600):
        try:
            from datetime import datetime, timedelta, timezone
            from splusthon import types
            from splusthon.tl import functions

            user = await self.client.get_input_entity(user_id)
            chat = await self.client.get_input_entity(chat_id)

            until_date = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

            rights = types.ChatBannedRights(
                until_date=until_date,
                send_messages=True
            )

            await self.client(functions.channels.EditBannedRequest(
                channel=chat,
                participant=user,
                banned_rights=rights
            ))

            self.logger.log_action(
                "MUTE",
                user_id,
                chat_id,
                f"به مدت {duration_seconds} ثانیه"
            )

            return True

        except Exception as e:
            print("MUTE ERROR:", repr(e))
            self.logger.log_error(f"خطا در سکوت کاربر: {e}")
            return False

'''

s = s[:start] + new_func + s[end:]

p.write_text(s, encoding="utf-8")
print("✅ mute_user replaced")
PY

python3 -m py_compile modules/admin_actions.py && echo "✅ syntax ok"
