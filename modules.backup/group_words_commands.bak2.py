
from modules.group_words_storage import add_word, remove_word, get_words


async def handle_group_word_command(bot, event, text, chat_id, user_id):

    print("FILTER DEBUG USER:", user_id)
    print("FILTER DEBUG ADMIN:", bot.config_manager.is_admin(user_id))
    text = text.strip()

    if not bot.config_manager.is_admin(user_id):
        try:
            if not bot.config_manager.is_admin(user_id):
                return False
        except Exception:
            return False

    # /فیلتر کلمه
    if text.startswith("/فیلتر "):
        word = text.replace("/فیلتر ", "", 1).strip()

        if word:
            if add_word(chat_id, word):
                await event.reply(f"✅ کلمه «{word}» فیلتر شد")
            else:
                await event.reply("⚠️ این کلمه قبلا فیلتر شده")
        return True


    # /رفع کلمه
    if text.startswith("/رفع "):
        word = text.replace("/رفع ", "", 1).strip()

        if word:
            if remove_word(chat_id, word):
                await event.reply(f"✅ کلمه «{word}» رفع فیلتر شد")
            else:
                await event.reply("⚠️ این کلمه در فیلترها نیست")
        return True


    # نمایش فیلترها
    if text == "/فیلترها":
        words = get_words(chat_id)

        if words:
            await event.reply(
                "📚 کلمات فیلتر شده:\n\n" +
                "\n".join(words)
            )
        else:
            await event.reply("📚 لیست فیلتر خالی است")

        return True


    return False
