from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.before_heavy_final_fix")
shutil.copy(p, backup)

start = text.find("if repeat_found:")
end = text.find("# بررسی کلمات فیلتر شده گروه", start)

if start == -1 or end == -1:
    print("❌ block پیدا نشد")
    exit()

new_block = '''if repeat_found:
                from modules.user_map import save_user

                save_user(chat_id, username, user_id)

                # حذف پیام های قبلی به صورت 100 تایی
                try:
                    ids = get_message_ids(chat_id, user_id)

                    if ids:
                        import asyncio

                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]

                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )
                            except Exception as ex:
                                print("bulk delete error:", ex)

                            await asyncio.sleep(0.2)

                        clear_user(chat_id, user_id)

                    else:
                        await bot.admin_actions.delete_message(
                            chat_id,
                            event=event
                        )

                except Exception as ex:
                    print("history delete error:", ex)

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    await bot.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                return

'''

text = text[:start] + new_block + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ heavy block replaced")
print("backup:", backup)
