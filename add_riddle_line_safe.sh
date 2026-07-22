#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if "RIDDLE_SAFE_INSERTED" in s:
    print("⚠️ already inserted")
    exit()

lines = s.splitlines(True)

for i, line in enumerate(lines):
    if "clean_text = message_text.strip()" in line:
        indent = line[:len(line)-len(line.lstrip())]

        code = (
            f"{indent}# RIDDLE_SAFE_INSERTED\n"
            f"{indent}if clean_text == \"چیستان\":\n"
            f"{indent}    try:\n"
            f"{indent}        q = new_riddle(chat_id, user_id)\n"
            f"{indent}        await event.reply(\"🧩 چیستان:\\n\\n\" + q + \"\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده\")\n"
            f"{indent}    except Exception as e:\n"
            f"{indent}        self.logger.log_error(f\"خطای چیستان: {{e}}\")\n"
            f"{indent}    return\n\n"
        )

        lines.insert(i+1, code)
        p.write_text("".join(lines), encoding="utf-8")
        print("✅ inserted after clean_text")
        break
else:
    print("❌ clean_text line not found")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
