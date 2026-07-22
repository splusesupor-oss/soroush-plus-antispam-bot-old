from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

start = s.index("    async def unban_user(")

# تا آخر تابع
end = s.find("\n    async def ", start+10)
if end == -1:
    end = len(s)

new = '''    async def unban_user(self, chat_id, user_id, username=None):
        try:
            from modules.banned_storage import remove_banned
            from splusthon.tl import functions, types

            remove_banned(chat_id, username or str(user_id))

            user = await self.client.get_entity(user_id)
            entity = await self.client.get_input_entity(chat_id)
            user_entity = await self.client.get_input_entity(user)

            await self.client(
                functions.channels.EditBannedRequest(
                    channel=entity,
                    participant=user_entity,
                    banned_rights=types.ChatBannedRights(
                        until_date=None,
                        view_messages=False,
                        send_messages=False,
                        send_media=False,
                        send_stickers=False,
                        send_gifs=False,
                        send_games=False,
                        send_inline=False,
                        embed_links=False,
                        send_polls=False,
                        change_info=False,
                        invite_users=False,
                        pin_messages=False
                    )
                )
            )

            self.logger.log_action(
                "UNBAN",
                user_id,
                chat_id,
                "رفع بن دائمی"
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در unban {user_id}: {e}")
            return False
'''

s = s[:start] + new + s[end:]

p.write_text(s, encoding="utf-8")
print("✅ رفع بن واقعی اصلاح شد")
