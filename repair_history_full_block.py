from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

backup=Path("handlers/message_handler.before_history_full_replace")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

start=None
end=None

for i,l in enumerate(lines):
    if "# ذخیره تاریخچه پیام برای ضد تکرار" in l:
        start=i
    if start and i>start and "# جستجوی وب" in l:
        end=i
        break

if start is None or end is None:
    print("❌ range not found")
    exit()

block = r'''
        # ذخیره تاریخچه پیام برای ضد تکرار
        try:
            save_history_message(
                chat_id,
                user_id,
                event.message.id,
                message_text
            )

            if is_repeat(chat_id, user_id, message_text):

                if getattr(bot, "_history_banned", None) == (chat_id, user_id):
                    return

                bot._history_banned = (chat_id, user_id)

                print("🚨 HISTORY REPEAT BAN:", user_id)

                ids = get_message_ids(chat_id, user_id)

                try:
                    for i in range(0, len(ids), 100):
                        batch = ids[i:i+100]
                        await bot.client.delete_messages(
                            chat_id,
                            batch
                        )
                        import asyncio
                        await asyncio.sleep(0.2)

                    print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")

                except Exception as err:
                    print("HISTORY DELETE ERROR:", err)

                try:
                    clear_user(chat_id, user_id)
                except Exception as err:
                    print("CLEAR HISTORY ERROR:", err)

                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")

                try:
                    await bot.admin_actions.ban_user(
                        chat_id,
                        user_id
                    )
                except Exception as err:
                    print("BAN ERROR:", err)

                return

        except Exception as e:
            pass
'''.strip("\n")

new_lines=block.splitlines()

lines[start:end]=new_lines

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ full history block repaired")
print("backup:",backup)
