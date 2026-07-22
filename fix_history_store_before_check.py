from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_store_fix")
backup.write_text(text,encoding="utf-8")

old="""if is_repeat(chat_id, user_id, message_text):"""

new="""# ذخیره همه پیام ها قبل از بررسی تکرار
try:
    save_history_message(
        chat_id,
        user_id,
        event.message.id,
        message_text
    )
except Exception as e:
    print("HISTORY SAVE ERROR:", e)

if is_repeat(chat_id, user_id, message_text):"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ history store moved before check")
    print("backup:",backup)
else:
    print("❌ marker not found")
