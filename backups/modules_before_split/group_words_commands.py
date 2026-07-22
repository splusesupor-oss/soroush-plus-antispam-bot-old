from modules.group_words_storage import add_word, remove_word, get_words
from modules.admin_storage import is_admin


async def handle_group_word_command(bot, event, text, chat_id, user_id, username=None):

    text = text.strip()

    if not username:
        try:
            sender = await event.get_sender()
            username = getattr(sender, "username", None)
        except Exception:
            username = None

    if not username:
        return False

    if not is_admin(chat_id, username):
        return False


    if text.startswith("/فیلتر "):
        word = text.replace("/فیلتر ", "", 1).strip()

        if word:
            if add_word(chat_id, word):
                await event.reply(f"✅ کلمه «{word}» برای این گروه فیلتر شد")
            else:
                await event.reply("⚠️ این کلمه قبلا برای این گروه ثبت شده")

            return True


    if text.startswith("/رفع "):
        word = text.replace("/رفع ", "", 1).strip()

        if word:
            if remove_word(chat_id, word):
                await event.reply(f"✅ کلمه «{word}» از فیلتر این گروه حذف شد")
            else:
                await event.reply("⚠️ این کلمه در فیلترها نیست")

            return True


    if text == "/فیلترها":

        words = get_words(chat_id)

        if words:
            await event.reply(
                "📋 کلمات فیلتر شده:\n\n" +
                "\n".join(words)
            )
        else:
            await event.reply("📋 هیچ کلمه‌ای فیلتر نشده")

        return True


    return False
