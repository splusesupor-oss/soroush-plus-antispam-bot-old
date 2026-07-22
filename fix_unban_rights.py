from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """                        banned_rights=types.ChatBannedRights(
                            until_date=None
                        )"""

new = """                        banned_rights=types.ChatBannedRights(
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
                        )"""

if old not in text:
    print("❌ الگو پیدا نشد.")
    raise SystemExit

text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("✅ unban اصلاح شد.")
