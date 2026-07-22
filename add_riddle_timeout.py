from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

marker = "    async def handle_new_message(self, event):"

func = '''    async def riddle_timeout_reply(self, event, chat_id, user_id):
        import asyncio
        from modules.riddles import get_answer, active_riddles

        await asyncio.sleep(50)

        answer = get_answer(chat_id, user_id)

        if answer:
            try:
                await event.reply(f"⏰ زمان چیستان تمام شد!\\n✅ پاسخ: {answer}")
                active_riddles.pop((chat_id, user_id), None)
            except Exception as e:
                self.logger.log_error(f"خطای ارسال پاسخ چیستان: {e}")

'''

if "async def riddle_timeout_reply" not in s:
    s = s.replace(marker, func + marker, 1)
    print("✅ تابع تایمر اضافه شد")
else:
    print("ℹ️ تابع موجود است")

p.write_text(s, encoding="utf-8")
