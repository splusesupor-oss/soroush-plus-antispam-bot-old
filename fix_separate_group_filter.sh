#!/bin/bash

FILE="main.py"

cp "$FILE" "$FILE.backup_before_separate_filter"

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''                from modules.group_words_storage import get_words
                from modules.group_banned_words_control import is_enabled

                if is_enabled(chat_id):
                    group_words = get_words(chat_id)

                    for word in group_words:
                        if word and word in message_text:
                            group_word_spam = True
                            group_word_reason = f"کلمه ممنوعه ({word})"
                            break
'''

new = '''                from modules.group_words_storage import get_words

                group_words = get_words(chat_id)

                for word in group_words:
                    if word and word in message_text:
                        group_word_spam = True
                        group_word_reason = f"فیلتر گروه ({word})"
                        break
'''

if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("✅ group filter separated successfully")
else:
    print("❌ target code not found")
    print("check manually around line 1166")

PY

python3 -m py_compile main.py && echo "✅ syntax ok"

