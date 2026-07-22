from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=None
end=None

for i,l in enumerate(lines):
    if "# ذخیره تاریخچه پیام برای ضد تکرار" in l:
        start=i
    if start is not None and "except Exception as e:" in l:
        end=i
        break

if start is None or end is None:
    print("❌ block not found")
    exit()

new_block = '''        # ذخیره تاریخچه پیام برای ضد تکرار
        try:
            save_history_message(
                chat_id,
                user_id,
                event.message.id,
                message_text
            )

            ids = get_message_ids(chat_id, user_id)

            if is_repeat(chat_id, user_id, message_text):

                print(f"🚨 HISTORY REPEAT BAN: {user_id}")

                if ids:
                    print(f"🧹 DELETE HISTORY COUNT={len(ids)}")

                    for i in range(0, len(ids), 100):
                        batch = ids[i:i+100]
                        try:
                            await bot.client.delete_messages(
                                chat_id,
                                batch
                            )
                        except Exception as err:
                            print("DELETE BATCH ERROR:", err)

                    print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")

                clear_user(chat_id, user_id)

                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")

                try:
                    await bot.admin_actions.ban_user(
                        chat_id,
                        user_id
                    )
                except Exception as err:
                    print("BAN ERROR:", err)

                return
'''

out=lines[:start]+new_block.splitlines()+lines[end:]

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ history block rebuilt")
