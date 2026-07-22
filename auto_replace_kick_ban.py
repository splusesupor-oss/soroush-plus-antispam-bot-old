from pathlib import Path
import shutil

f = Path("main.py")

backup = "main.py.before_kick_to_ban_fix"
shutil.copy(f, backup)

s = f.read_text(encoding="utf-8")

old = """await self.client.kick_participant(
                            chat_id,
                            target_user
                        )"""

new = """await self.client.edit_permissions(
                            chat_id,
                            target_user,
                            until_date=None,
                            view_messages=False
                        )"""

if old in s:
    s=s.replace(old,new)
    f.write_text(s,encoding="utf-8")
    print("✅ kick تبدیل شد به بن واقعی")
else:
    print("❌ الگو پیدا نشد")

print("📦 بکاپ:",backup)
