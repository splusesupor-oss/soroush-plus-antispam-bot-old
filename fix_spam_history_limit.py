from pathlib import Path

p = Path("modules/spam_history.py")
text = p.read_text(encoding="utf-8")

old = """def is_repeat(chat_id, user_id, text, limit=3):
    key = (chat_id, user_id)
    current = normalize(text)

    if not current:
        return False

    history = MESSAGE_HISTORY.get(key, [])
    count = history.count(current)

    return count >= limit
"""

new = """def is_repeat(chat_id, user_id, text, limit=3):
    key = (chat_id, user_id)
    current = normalize(text)

    if not current:
        return False

    history = MESSAGE_HISTORY.get(key, [])

    count = history.count(current)

    # جلوگیری از انتظار برای صدها پیام
    # بعد از 3 پیام مشابه فعال شود
    if count >= limit:
        return True

    # پیام‌های خیلی طولانی یا تبلیغ تکراری
    if len(current) > 250:
        return True

    return False
"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ spam repeat limit fixed")
else:
    print("❌ block not found")
