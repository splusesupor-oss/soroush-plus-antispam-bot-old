from pathlib import Path

p = Path("core/bot_working_split_ok.py")
text = p.read_text(encoding="utf-8")

line = "from modules.security.security_manager import check_security, remove_message\n"

if line not in text:
    text = line + text

p.write_text(text, encoding="utf-8")

print("✅ security manager import connected")
