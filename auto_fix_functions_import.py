from pathlib import Path
import shutil, datetime

file = Path("handlers/message_handler.py")

backup = Path(
    "handlers/message_handler.before_functions_import_" +
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
)

shutil.copy(file, backup)

text = file.read_text(encoding="utf-8")

if "from telethon import functions" not in text:
    lines = text.splitlines()

    insert = 0
    for i,line in enumerate(lines):
        if line.startswith("from telethon") or line.startswith("import"):
            insert = i+1

    lines.insert(insert, "from telethon import functions")
    text = "\n".join(lines) + "\n"

    file.write_text(text, encoding="utf-8")
    print("✅ import functions اضافه شد")
else:
    print("⏭ functions قبلا وجود دارد")

print("📌 بکاپ:", backup)
