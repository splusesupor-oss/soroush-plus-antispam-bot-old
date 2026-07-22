from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

insert=1311

lines[insert:insert]=[
"            except Exception as e:",
"                print('خطای بررسی فوروارد:', e)",
""
]

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
