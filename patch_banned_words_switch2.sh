#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
p="modules/spam_detector.py"

s=open(p,encoding="utf-8").read()

if "from modules.group_banned_words_control import is_enabled" not in s:
    s=s.replace(
        "import re",
        "import re\nfrom modules.group_banned_words_control import is_enabled"
    )

s=s.replace(
"def check_banned_words(self, text: str) -> Tuple[bool, Optional[str]]:",
"def check_banned_words(self, text: str, chat_id=None) -> Tuple[bool, Optional[str]]:"
)

old="""        if not self.config.get("check_banned_words", True):
            return False, None

        text_lower = text.lower()"""

new="""        if not self.config.get("check_banned_words", True):
            return False, None

        if chat_id is not None and not is_enabled(chat_id):
            return False, None

        text_lower = text.lower()"""

if old not in s:
    print("INSERT TARGET NOT FOUND")
else:
    s=s.replace(old,new)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile modules/spam_detector.py && echo "BANNED WORD SWITCH 2 OK"
