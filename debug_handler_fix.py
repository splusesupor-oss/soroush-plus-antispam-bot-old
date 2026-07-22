from pathlib import Path
import re

p = Path("handlers/message_handler.py")
t = p.read_text(encoding="utf-8")

# fix missing sender/chat_id order at start
old = '''    # اطلاعات پیام
    # ===== SECURITY MANAGER ====='''

new = '''    # اطلاعات پیام
    chat_id = getattr(event, "chat_id", None)
    sender = await event.get_sender()
    user_id = sender.id if sender else 0
    username = getattr(sender, "username", None) or "Unknown"

    # ===== SECURITY MANAGER ====='''

if old in t and "chat_id = getattr(event, \"chat_id\"" not in t[:1200]:
    t = t.replace(old,new,1)

# fix web search position if broken
if "if clean_text.startswith(\"جستجو \")" not in t:
    backup = Path("handlers/message_handler.py.FINAL_SAFE")
    if backup.exists():
        b = backup.read_text(encoding="utf-8")
        m = re.search(r"# جستجوی وب(.*?)# پاسخ خودکار",b,re.S)
        if m:
            t = t.replace(
                "# پاسخ خودکار پیام‌ها",
                "# جستجوی وب"+m.group(1)+"\n\n# پاسخ خودکار پیام‌ها",
                1
            )

p.write_text(t,encoding="utf-8")
print("FIXED")
