#!/bin/bash

cp main.py main.py.backup_filter_split

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = None

            try:
                from modules.group_words_storage import get_words
                from modules.group_banned_words_control import is_enabled

                if is_enabled(chat_id):
                    group_words = get_words(chat_id)

                    for word in group_words:
                        if word and word in message_text:
                            group_word_spam = True
                            group_word_reason = f"کلمه ممنوعه ({word})"
                            break

            except Exception as e:
                self.logger.log_error(f"خطای بررسی کلمات گروه: {e}")
'''

new = '''            # فیلترهای گروه جدا از کلمات ممنوعه
            group_word_spam = False
            group_word_reason = None

            try:
                from modules.group_words_storage import get_words

                group_words = get_words(chat_id)

                for word in group_words:
                    if word and word in message_text:
                        group_word_spam = True
                        group_word_reason = f"فیلتر گروه ({word})"
                        break

            except Exception as e:
                self.logger.log_error(f"خطای بررسی فیلتر گروه: {e}")
'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("OK: filters separated")
else:
    print("BLOCK NOT FOUND")
PY

python3 -m py_compile main.py && echo "syntax ok"
