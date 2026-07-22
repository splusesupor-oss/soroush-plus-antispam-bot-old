#!/data/data/com.termux/files/usr/bin/bash

cp modules/spam_detector.py modules/spam_detector.py.before_chatid_fix

python3 - <<'PY'
p="modules/spam_detector.py"
s=open(p,encoding="utf-8").read()

s=s.replace(
"self.check_banned_words(text)",
"self.check_banned_words(text, chat_id)"
)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile modules/spam_detector.py && echo "BANNED CHATID CALLS FIX OK"
