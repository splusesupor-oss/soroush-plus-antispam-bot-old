#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
p="modules/spam_detector.py"

s=open(p,encoding="utf-8").read()

s=s.replace(
"is_banned, reason_banned = self.check_banned_words(text)",
"is_banned, reason_banned = self.check_banned_words(text, chat_id)"
)

s=s.replace(
"def is_spam(self, text: str) -> Tuple[bool, str]:",
"def is_spam(self, text: str, chat_id=None) -> Tuple[bool, str]:"
)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile modules/spam_detector.py && echo "BANNED CHAT ID FIX OK"
