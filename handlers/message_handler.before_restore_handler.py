async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            name = (
                getattr(user, "username", None)
                or getattr(user, "first_name", None)
                or str(getattr(user, "id", ""))
            )

            participant = getattr(user, "participant", None)

            if participant:
                kind = type(participant).__name__.lower()

                if "creator" in kind:
                    owner = name
                elif "admin" in kind:
                    admins.append(name)

    except Exception as e:
        return f"خطا: {e}"

    msg = f"مالک گروه: {owner}\n\nادمین های گروه:\n"

    if admins:
        for i, a in enumerate(admins, 1):
            msg += f"{i}- {a}\n"
    else:
        msg += "ندارد\n"

    return msg



