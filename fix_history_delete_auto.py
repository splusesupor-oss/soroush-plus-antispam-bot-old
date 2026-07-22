from pathlib import Path

p=Path("handlers/message_handler.py")

t=p.read_text(encoding="utf-8")


old='''                if ids:
                    await bot.client.delete_messages(
                        chat_id,
                        ids
                    )
'''

new='''                if ids:
                    try:
                        # حذف دسته ای پیام ها
                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]
                            await bot.client.delete_messages(
                                chat_id,
                                batch
                            )
                    except Exception as err:
                        print("HISTORY DELETE ERROR:", err)
'''


if old in t:
    t=t.replace(old,new)
    print("✅ delete batch fixed")
else:
    print("❌ delete block not found")


# جلوگیری از چند بار بن پشت سر هم
old2='''                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")
                await bot.admin_actions.ban_user(
                    chat_id,
                    user_id
                )
'''

new2='''                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")

                try:
                    await bot.admin_actions.ban_user(
                        chat_id,
                        user_id
                    )
                except Exception as err:
                    print("BAN ERROR:", err)
'''

if old2 in t:
    t=t.replace(old2,new2)
    print("✅ ban guard fixed")


p.write_text(t,encoding="utf-8")
print("DONE")
