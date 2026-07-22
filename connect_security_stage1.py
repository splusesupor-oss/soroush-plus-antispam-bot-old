from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

imports = """
from modules.security.security_manager import check_security, remove_message
"""

if "from modules.security.security_manager import check_security, remove_message" not in text:
    lines = text.splitlines()
    pos = 0
    while pos < len(lines) and lines[pos].startswith("from "):
        pos += 1
    lines.insert(pos, imports.strip())
    text = "\n".join(lines)

p.write_text(text, encoding="utf-8")
print("✅ stage1 connected")
