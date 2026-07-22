from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

bad = '''            # اجرای دستورات مدیریتی
            if clean_text.startswith(("!", "/", ".")):
                try:
                    sender = await event.get_sender()
                    await self.handle_admin_commands(
                        event,
                        clean_text,
                        getattr(sender, "id", 0),
                        chat_id
                    )
                    return
                except Exception as e:
                    self.logger.log_error(f"خطای اجرای دستور مدیر: {e}")
'''

s = s.replace(bad, "")

needle = '            chat_id = getattr(chat, "id", None)\n'

add = '''            chat_id = getattr(chat, "id", None)

            # اجرای دستورات مدیریتی
            if clean_text.startswith(("!", "/", ".")):
                try:
                    sender = await event.get_sender()
                    await self.handle_admin_commands(
                        event,
                        clean_text,
                        getattr(sender, "id", 0),
                        chat_id
                    )
                    return
                except Exception as e:
                    self.logger.log_error(f"خطای اجرای دستور مدیر: {e}")
'''

if needle not in s:
    print("❌ خط chat_id پیدا نشد")
else:
    s = s.replace(needle, add, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ جای دستورهای مدیر اصلاح شد")
