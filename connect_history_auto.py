from pathlib import Path

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

# بکاپ
Path("backups/before_connect_history.py").write_text(text, encoding="utf-8")

imp = "from modules.spam_history import add_message, is_repeat, get_message_ids, clear_user\n"

if "from modules.spam_history import" not in text:
    lines = text.splitlines()

    # بعد از import های اول اضافه کن
    pos = 0
    for i,l in enumerate(lines):
        if l.startswith("from ") or l.startswith("import "):
            pos = i + 1

    lines.insert(pos, imp.rstrip())

    p.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("✅ spam_history connected")
else:
    print("⚠️ already connected")
