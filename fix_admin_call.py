from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

needle = '            clean_text = message_text.strip()\n'

insert = '''            clean_text = message_text.strip()\n\n            # اجرای دستورات مدیریتی\n            if clean_text.startswith(("!", "/", ".")):\n                try:\n                    sender = await event.get_sender()\n                    await self.handle_admin_commands(\n                        event,\n                        clean_text,\n                        getattr(sender, "id", 0),\n                        chat_id\n                    )\n                    return\n                except Exception as e:\n                    self.logger.log_error(f"خطای اجرای دستور مدیر: {e}")\n'''

if needle not in s:
    print("❌ محل پیدا نشد")
else:
    s = s.replace(needle, insert, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ اتصال دستورات مدیر اضافه شد")
