from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

if "from modules.media_spam_detector import check_media_spam" not in text:
    text = "from modules.media_spam_detector import check_media_spam\n" + text

old = '    message_text = getattr(event.message, "message", "") or ""'

new = '''    # بررسی اسپم رسانه‌ای
    try:
        if check_media_spam(event.message):
            await bot.client.delete_messages(event.chat_id, [event.message.id])
            return
    except Exception as e:
        bot.logger.log_error(f"media spam error: {e}")

    message_text = getattr(event.message, "message", "") or ""'''

if "media spam error" not in text and old in text:
    text = text.replace(old, new)

p.write_text(text, encoding="utf-8")
print("✅ media safe connected")
