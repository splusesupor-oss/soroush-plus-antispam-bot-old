from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = "async def handle_new_message(bot, event):"

new = """from modules.anti_attack import AntiAttack
from modules.delete_queue import DeleteQueue

anti_attack = AntiAttack()
delete_queue = None

async def handle_new_message(bot, event):"""

if "from modules.anti_attack import AntiAttack" not in text:
    text = text.replace(old, new)


marker = "message_text = getattr(event.message, \"message\", \"\") or \"\""

insert = """
    global delete_queue

    if delete_queue is None:
        delete_queue = DeleteQueue(bot.client)

    sender_check = await event.get_sender()
    uid_check = sender_check.id if sender_check else 0

    if anti_attack.check(event.chat_id, uid_check):
        await delete_queue.add(
            event.chat_id,
            event.message.id
        )
        await delete_queue.delete_now(event.chat_id)
        return

    try:
        if hasattr(event.message, "file") or hasattr(event.message, "photo"):
            if hasattr(bot, "spam_detector") and bot.spam_detector.check_media_spam(event.message):
                await delete_queue.add(
                    event.chat_id,
                    event.message.id
                )
                await delete_queue.delete_now(event.chat_id)
                return
    except Exception as e:
        print("media security error:", e)

"""

if "anti_attack.check" not in text:
    text = text.replace(marker, marker + insert)


p.write_text(text, encoding="utf-8")
print("✅ security systems connected")
