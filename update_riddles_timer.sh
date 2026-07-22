#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("modules/riddles.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
"import random",
"import random\nimport time"
)

s = s.replace(
"active_riddles = {}",
"active_riddles = {}\nRIDDLE_TIMEOUT = 50"
)

s = s.replace(
"active_riddles[(chat_id, user_id)] = a",
"active_riddles[(chat_id, user_id)] = {\n        'answer': a,\n        'time': time.time()\n    }"
)

s = s.replace(
"if key in active_riddles:\n        if answer.strip() == active_riddles[key]:\n            del active_riddles[key]",
"if key in active_riddles:\n        data = active_riddles[key]\n\n        if time.time() - data['time'] > RIDDLE_TIMEOUT:\n            del active_riddles[key]\n            return False\n\n        if answer.strip() == data['answer']:\n            del active_riddles[key]"
)

s = s.replace(
"return active_riddles.get((chat_id, user_id))",
"data = active_riddles.get((chat_id, user_id))\n    if data:\n        return data['answer']\n    return None"
)

p.write_text(s, encoding="utf-8")

print("✅ timer 50 seconds added")
PY

python3 -m py_compile modules/riddles.py && echo "✅ syntax ok"
