from pathlib import Path

p = Path("modules/admin_actions.py")
text = p.read_text(encoding="utf-8")

if "async def unban_user(" in text:
    print("✅ unban_user از قبل وجود دارد.")
    raise SystemExit

insert = '''

    async def unban_user(self, chat_id, user_id) -> bool:
        try:
            from splusthon import types
            from splusthon.tl import functions

            user = await self.client.get_entity(user_id)

            await self.client(
                functions.channels.EditBannedRequest(
                    channel=await self.client.get_input_entity(chat_id),
                    participant=user,
                    banned_rights=types.ChatBannedRights(
                        until_date=None
                    )
                )
            )

            self.logger.log_action("UNBAN", user_id, chat_id)
            return True

        except Exception as e:
            self.logger.log_error(f"خطا در unban {user_id}: {e}")
            return False

'''

marker = "async def ban_user("
pos = text.find(marker)

if pos == -1:
    print("❌ ban_user پیدا نشد.")
    raise SystemExit

text = text[:pos] + insert + text[pos:]

p.write_text(text, encoding="utf-8")
print("✅ unban_user اضافه شد.")
