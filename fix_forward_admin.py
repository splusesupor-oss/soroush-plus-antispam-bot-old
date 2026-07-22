from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

old = '''        # حذف پیام های فوروارد شده
        try:
            if getattr(event.message, "fwd_from", None):
                await bot.client.delete_messages(
'''

new = '''        # حذف پیام های فوروارد شده (به جز ادمین)
        try:
            from modules.admin_storage import is_admin

            if getattr(event.message, "fwd_from", None):

                if is_admin(chat_id, username):
                    print(f"✅ ADMIN FORWARD BYPASS: {username}")
                    return

                await bot.client.delete_messages(
'''

if old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("✅ فوروارد ادمین محافظت شد")
else:
    print("❌ بخش پیدا نشد")
