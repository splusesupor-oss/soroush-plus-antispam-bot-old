


async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            username = getattr(user, "username", None)
            name = username or getattr(user, "first_name", None) or str(getattr(user, "id", ""))

            participant = getattr(user, "participant", None)

