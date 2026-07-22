from pathlib import Path
import shutil

p = Path("modules/admin_actions.py")

if not p.exists():
    print("❌ فایل پیدا نشد")
    exit()

backup = "modules/admin_actions.before_ban_fix.py"
shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = '''            user = await self.client.get_entity(user_id)

            await self.client.kick_participant(
                chat_id,
                user
            )
'''

new = '''            from splusthon import types
            from splusthon.tl import functions

            user = await self.client.get_entity(user_id)

            await self.client(
                functions.channels.EditBannedRequest(
                    channel=await self.client.get_input_entity(chat_id),
                    participant=user,
                    banned_rights=types.ChatBannedRights(
                        until_date=None,
                        view_messages=True
                    )
                )
            )
'''

if old not in s:
    print("❌ بخش ban_user پیدا نشد")
    exit()

s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")

print("✅ اصلاح اخراج انجام شد")
print("📦 بکاپ:", backup)
