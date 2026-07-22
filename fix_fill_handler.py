from pathlib import Path

p=Path("handlers/message_handler.py")
s=p.read_text()

if "from modules.fill_blank" not in s:
    s=s.replace(
        "from modules.admin_storage import is_admin",
        "from modules.admin_storage import is_admin\nfrom modules.fill_blank import new_fill, check_fill, get_fill_answer"
    )

insert='''
        # بازی جای خالی
        if clean_text == "جای خالی":
            try:
                q = new_fill(chat_id, user_id)
                await event.reply("📝 جای خالی:\\n\\n" + q + "\\n\\n⏳ ۳۰ ثانیه فرصت داری")

                async def fill_timer():
                    import asyncio
                    await asyncio.sleep(30)
                    ans = get_fill_answer(chat_id, user_id)
                    if ans:
                        await event.reply(f"⏰ زمان تمام شد!\\n✅ پاسخ: {ans}")

                asyncio.create_task(fill_timer())

            except Exception as e:
                bot.logger.log_error(f"خطای جای خالی: {e}")
            return
'''

if "# بازی جای خالی" not in s:
    s=s.replace(
        "        # RIDDLE_SAFE_INSERTED",
        insert+"\n        # RIDDLE_SAFE_INSERTED"
    )

p.write_text(s)
print("DONE")
