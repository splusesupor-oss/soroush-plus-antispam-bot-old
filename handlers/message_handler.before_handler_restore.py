async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        print("ADMIN DEBUG CHAT:", chat_id)

        async for user in bot.client.iter_participants(chat_id, limit=100):
            print(
                "USER:",
                getattr(user, "id", None),
                getattr(user, "username", None),
                type(getattr(user, "participant", None)).__name__
            )

            part = getattr(user, "participant", None)

            if part:
                t = type(part).__name__.lower()

                if "creator" in t:
                    owner = getattr(user, "username", None) or str(user.id)

                elif "admin" in t:
                    admins.append(
                        getattr(user, "username", None) or str(user.id)
                    )

    except Exception as e:
        print("ADMIN ERROR:", e)

    msg = f"مالک گروه: {owner}\n\nادمین های گروه:\n"

    if admins:
        for i,a in enumerate(admins,1):
            msg += f"{i}- {a}\n"
    else:
        msg += "ندارد\n"

    return msg


async def main():
    bot = SoroushAntiSpamBot()
    await bot.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


