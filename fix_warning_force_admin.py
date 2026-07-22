from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = '''sender = await event.get_sender()
            sender_username = getattr(sender, "username", None)

            if not is_admin(chat_id, sender_username):'''

new = '''sender = await event.get_sender()
            sender_username = getattr(sender, "username", None)

            from modules.admin_storage import is_admin as real_is_admin

            if not real_is_admin(chat_id, sender_username):'''

if old in text:
    text = text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ بررسی ادمین اخطار اجباری شد")
else:
    print("❌ محل پیدا نشد")
