from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''await self.client.delete_messages(
                                chat_id,
                                ids
                            )
'''

new = '''await self.client.delete_messages(
                                chat_id,
                                ids
                            )

                            try:
                                from modules.group_stats import add_deleted
                                add_deleted(chat_id, user_id, username)
                            except Exception:
                                pass
'''

count = s.count(old)

if count == 0:
    print("❌ محل حذف پیام پیدا نشد")
else:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ آمار حذف برای پاک عدد اضافه شد")

