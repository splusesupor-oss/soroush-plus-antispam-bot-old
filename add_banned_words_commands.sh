#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_banned_words_control_fix

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

# import
old="from modules.group_words_commands import handle_group_word_command"
new="""from modules.group_words_commands import handle_group_word_command
from modules.group_banned_words_control import enable, disable"""

if "from modules.group_banned_words_control import enable, disable" not in s:
    s=s.replace(old,new)


# command block
marker="async def handle_admin_commands(self, event, text: str, admin_id: int, chat_id: int):"

block="""
        if text == "لغو کلمات ممنوعه":
            disable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")
            return

        if text == "فعال کلمات ممنوعه":
            enable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")
            return

"""

if "لغو کلمات ممنوعه" not in s:
    s=s.replace(marker, marker + "\n" + block)


open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "BANNED WORD COMMANDS OK"
