#!/data/data/com.termux/files/usr/bin/bash

cp modules/spam_detector.py modules/spam_detector.py.before_group_switch

python3 - <<'PY'
p="modules/spam_detector.py"

s=open(p,encoding="utf-8").read()

if "group_banned_words_control import is_enabled" not in s:
    s=s.replace(
        "import os",
        "import os\nfrom modules.group_banned_words_control import is_enabled"
    )

old="""    def check_banned_words(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.config.get("check_banned_words", True):
            return False, None

        for word in self.config.banned_words:"""

new="""    def check_banned_words(self, text: str, chat_id=None) -> Tuple[bool, Optional[str]]:
        if not self.config.get("check_banned_words", True):
            return False, None

        if chat_id is not None and not is_enabled(chat_id):
            return False, None

        for word in self.config.banned_words:"""

if old not in s:
    print("TARGET NOT FOUND")
    exit()

s=s.replace(old,new)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile modules/spam_detector.py && echo "BANNED WORD SWITCH PATCH OK"
