from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

if "from modules.media_spam_detector import check_media_spam" not in text:
    text = text.replace(
        "from modules.group_stats import add_message",
        "from modules.group_stats import add_message\nfrom modules.media_spam_detector import check_media_spam"
    )

marker = '    # اطلاعات پیام\n'

block = '''    # بررسی اسپم تصویری و فایل\n    try:\n        if check_media_spam(event.message):\n            await bot.client.delete_messages(event.chat_id, [event.message.id])\n            return\n    except Exception as e:\n        bot.logger.log_error(f"media spam error: {e}")\n\n'''

if "media spam error" not in text:
    text = text.replace(marker, block + marker)

p.write_text(text, encoding="utf-8")

print("✅ media spam connected")
