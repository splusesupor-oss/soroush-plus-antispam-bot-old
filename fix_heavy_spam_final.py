from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = '''if repeat_found:
                                from modules.user_map import save_user
                                save_user(chat_id, username, user_id)

                                await bot.admin_actions.delete_message(
                                    chat_id,
                                    event=event
                                )

                                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                                # ذخیره پیام اسپم برای حذف کامل
                                try:
                                    if not hasattr(bot, "spammer_messages"):
                                        bot.spammer_messages = {}

                                    if user_id not in bot.spammer_messages:
                                        bot.spammer_messages[user_id] = []

                                    bot.spammer_messages[user_id].append(event.message.id)

                                    # حذف سریع همه پیام های ذخیره شده
                                    ids = list(bot.spammer_messages[user_id])
                                    if ids:
                                        await bot.client.delete_messages(ids)

                                    bot.spammer_messages[user_id] = []

                                except Exception as e:
                                    print("SPAM DELETE HISTORY ERROR:", e)

                                punish_key = f"{chat_id}:{user_id}"

                                if punish_key not in bot.punished_users:
                                    bot.punished_users.add(punish_key)

                                    await bot.admin_actions.punish_user(
                                        chat_id,
                                        user_id,
                                        username
                                    )

                                return'''

new = '''if repeat_found:
                                from modules.user_map import save_user
                                save_user(chat_id, username, user_id)

                                try:
                                    if not hasattr(bot, "spammer_messages"):
                                        bot.spammer_messages = {}

                                    if user_id not in bot.spammer_messages:
                                        bot.spammer_messages[user_id] = []

                                    bot.spammer_messages[user_id].append(event.message.id)

                                    ids = list(bot.spammer_messages[user_id])

                                    await bot.client.delete_messages(
                                        chat_id,
                                        ids
                                    )

                                    bot.spammer_messages[user_id].clear()

                                except Exception as e:
                                    print("SPAM DELETE ERROR:", e)

                                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                                try:
                                    await bot.admin_actions.ban_user(
                                        chat_id,
                                        user_id
                                    )
                                except:
                                    await bot.admin_actions.punish_user(
                                        chat_id,
                                        user_id,
                                        username
                                    )

                                return'''

if old not in text:
    print("❌ block پیدا نشد")
else:
    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print("✅ heavy spam fix applied")
