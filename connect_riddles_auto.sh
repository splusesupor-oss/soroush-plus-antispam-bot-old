#!/bin/bash

python3 <<'PY'
from pathlib import Path

p = Path("main.py")

if not p.exists():
    print("❌ main.py not found")
    exit()

s = p.read_text(encoding="utf-8")

# import
if "from modules.riddles import" not in s:
    marker = "import "
    lines = s.splitlines()
    pos = 0
    while pos < len(lines) and (lines[pos].startswith("import ") or lines[pos].startswith("from ")):
        pos += 1

    lines.insert(pos, "from modules.riddles import new_riddle, check_answer, get_answer")
    s = "\n".join(lines) + "\n"


# add state
if "RIDDLE_TIMEOUT" not in s:
    s = s.replace(
        "class ",
        "RIDDLE_TIMEOUT = 50\n\nclass ",
        1
    )


# handler before normal message handling
if "چیستان" not in s:
    marker = "        # بررسی کلمات فیلتر شده گروه"

    code = '''
        # ===== RIDDLE SYSTEM =====
        if message_text.strip() == "چیستان":
            try:
                q = new_riddle(chat_id, user_id)
                await event.reply("🧩 چیستان:\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری")
                continue
            except Exception:
                pass

        answer = get_answer(chat_id, user_id)
        if answer and check_answer(chat_id, user_id, message_text):
            await event.reply("✅ آفرین! جواب درست بود")
            continue
        # ===== END RIDDLE =====

'''
    if marker in s:
        s = s.replace(marker, code + marker, 1)
    else:
        print("⚠️ handler marker not found")


p.write_text(s, encoding="utf-8")
print("✅ riddles connected")

PY

python3 -m py_compile main.py && echo "✅ syntax ok"

