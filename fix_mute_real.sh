#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"

cp modules/admin_actions.py modules/admin_actions_backup_mute.py

python3 - <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

start = s.index("    async def mute_user")
end = s.index("    async def ban_user")

new = r'''    async def mute_user(self, chat_id, user_id, duration_seconds=3600):
        try:
            from datetime import datetime, timedelta, timezone
            from splusthon import types
            from splusthon.tl import functions

            chat = await self.client.get_entity(chat_id)
            user = await self.client.get_entity(user_id)

            channel = types.InputChannel(
                chat.id,
                chat.access_hash
            )

            participant = types.InputUser(
                user.id,
                user.access_hash
            )

            rights = types.ChatBannedRights(
                until_date=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds),
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                send_polls=True
            )

            await self.client(functions.channels.EditBannedRequest(
                channel=channel,
                participant=participant,
                banned_rights=rights
            ))

            self.logger.log_action(
                "MUTE",
                user_id,
                chat_id,
                f"{duration_seconds} seconds"
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در سکوت کاربر: {e}")
            return False


    async def unmute_user(self, chat_id, user_id):
        try:
            from splusthon import types
            from splusthon.tl import functions

            chat = await self.client.get_entity(chat_id)
            user = await self.client.get_entity(user_id)

            channel = types.InputChannel(
                chat.id,
                chat.access_hash
            )

            participant = types.InputUser(
                user.id,
                user.access_hash
            )

            rights = types.ChatBannedRights(
                until_date=None
            )

            await self.client(functions.channels.EditBannedRequest(
                channel=channel,
                participant=participant,
                banned_rights=rights
            ))

            self.logger.log_action(
                "UNMUTE",
                user_id,
                chat_id
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در رفع سکوت: {e}")
            return False

'''

p.write_text(s[:start] + new + s[end:], encoding="utf-8")
print("MUTE PATCHED")
PY

python3 -m py_compile modules/admin_actions.py && echo "OK"
