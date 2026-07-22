from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_remove_duplicate_deactivate.py")

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old='''                    deactivate_group(gid, title)
                    await event.respond(
                        f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                    )'''

if old in text:
    text=text.replace(old,'',1)
else:
    print("not found")

p.write_text(text,encoding="utf-8")

print("✅ duplicate removed")
print("backup:",backup)
