from pathlib import Path

p = Path("core/bot_working_split_ok.py")
text = p.read_text(encoding="utf-8")

needle = '''        text = (event.message.message or "").strip()

        # کنترل فعال بودن گروه
'''

insert = '''        text = (event.message.message or "").strip()

        # آزاد کردن کاربر محروم شده
        if text == "آزاد":
            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await self.client.get_messages(
                    event.chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                entity = await self.client.get_input_entity(event.chat_id)
                user_entity = await self.client.get_input_entity(user)

                await self.client(
                    functions.channels.EditBannedRequest(
                        channel=entity,
                        participant=user_entity,
                        banned_rights=types.ChatBannedRights(
                            until_date=None,
                            view_messages=False,
                            send_messages=False,
                            send_media=False,
                            send_stickers=False,
                            send_gifs=False,
                            send_games=False,
                            send_inline=False,
                            embed_links=False,
                            send_polls=False,
                            change_info=False,
                            invite_users=False,
                            pin_messages=False
                        )
                    )
                )

                username = getattr(user, "username", None)

                if username:
                    remove_banned(event.chat_id, username)
                else:
                    remove_banned(event.chat_id, str(user.id))

                await event.reply("♻️ کاربر آزاد شد")

            except Exception as e:
                await event.reply(f"❌ خطا در آزاد کردن:\\n{e}")

            return

        # کنترل فعال بودن گروه
'''

if needle not in text:
    print("❌ محل پیدا نشد")
else:
    text = text.replace(needle, insert, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ دستور آزاد به فایل فعال اضافه شد")
