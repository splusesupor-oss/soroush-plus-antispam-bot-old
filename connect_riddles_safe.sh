#!/bin/bash

cp main.py main.py.before_riddle_safe

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if "from modules.riddles import" not in s:
    s = s.replace(
        "import asyncio",
        "import asyncio\nfrom modules.riddles import new_riddle, check_answer, get_answer",
        1
    )

marker = "    async def handle_new_message"

if "RIDDLE_SYSTEM_CONNECTED" not in s:
    insert = '''
        # RIDDLE_SYSTEM_CONNECTED
        if message_text.strip() == "چیستان":
            try:
                q = new_riddle(chat_id, sender_id)
                await event.reply(
                    "🧩 چیستان:\\n\\n"
                    + q
                    + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بدی"
                )
                return
            except Exception as e:
                self.logger.log_error(f"riddle error: {e}")

'''
    pos = s.find(marker)
    if pos != -1:
        # پیدا کردن اولین خط بعد از def
        start = s.find("\n", pos)+1
        s = s[:start] + insert + s[start:]

p.write_text(s, encoding="utf-8")
PY

python3 -m py_compile main.py

if [ $? -ne 0 ]; then
    echo "❌ error detected restoring backup"
    cp main.py.before_riddle_safe main.py
    exit 1
fi

echo "✅ riddles safely connected"
