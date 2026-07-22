from pathlib import Path
import shutil,re

f=Path("main.py")
backup="main.py.before_kick_regex_fix"

shutil.copy(f,backup)

s=f.read_text(encoding="utf-8")

pattern=r"await self\.client\.kick_participant\(\s*chat_id,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)"

def repl(m):
    user=m.group(1)
    return f"""await self.client.edit_permissions(
                            chat_id,
                            {user},
                            until_date=None,
                            view_messages=False
                        )"""

ns,n=re.subn(pattern,repl,s)

if n:
    f.write_text(ns,encoding="utf-8")
    print("✅ تبدیل شد:",n)
else:
    print("❌ هیچ kick_participant با chat_id پیدا نشد")

print("📦 بکاپ:",backup)
