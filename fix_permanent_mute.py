from pathlib import Path
import re

p = Path("modules/admin_actions.py")

text = p.read_text(encoding="utf-8")

old = """rights = types.ChatBannedRights(
                until_date=until_date,
                send_messages=True
            )"""

new = """rights = types.ChatBannedRights(
                until_date=until_date,
                view_messages=False,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )"""

if old not in text:
    print("❌ بخش قدیمی پیدا نشد")
    exit()

text = text.replace(old, new)

# دائمی کردن پیش‌فرض سکوت
text = text.replace(
    "async def mute_user(self, chat_id, user_id, duration_seconds=None):",
    "async def mute_user(self, chat_id, user_id, duration_seconds=None):"
)

p.write_text(text, encoding="utf-8")

print("✅ سکوت دائمی اصلاح شد")
