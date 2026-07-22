from pathlib import Path
import re

p = Path("modules/spam_history.py")
text = p.read_text(encoding="utf-8")

pattern = r"def is_repeat\(chat_id, user_id, text, limit=3\):.*?(?=\ndef get_message_ids)"

new = '''def is_repeat(chat_id, user_id, text, limit=3):
    key = (chat_id, user_id)
    current = normalize(text)

    if not current:
        return False

    history = MESSAGE_HISTORY.get(key, [])

    count = history.count(current)

    # تکرار سریع پیام
    if count >= limit:
        return True

    # تبلیغ یا متن بسیار بلند
    if len(current) > 250:
        return True

    return False
'''

new_text, n = re.subn(pattern, new, text, flags=re.S)

if n:
    p.write_text(new_text, encoding="utf-8")
    print("✅ is_repeat replaced")
else:
    print("❌ function not found")
