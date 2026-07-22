#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

s=s.replace(
"is_spam, reason = self.detector.is_spam(message_text)",
"is_spam, reason = self.detector.is_spam(message_text, chat_id)"
)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "MAIN CHAT ID FIX OK"
