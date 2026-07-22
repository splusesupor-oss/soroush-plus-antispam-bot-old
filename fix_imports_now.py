from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

insert = """from modules.riddles import check_answer
from modules.group_stats import add_message
"""

if "from modules.riddles import check_answer" not in text:
    text = insert + "\n" + text

p.write_text(text, encoding="utf-8")
print("✅ imports added")
