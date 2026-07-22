from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

marker = """            # RIDDLE_SAFE_INSERTED"""

insert = """            # بررسی جواب چیستان
            try:
                if check_answer(chat_id, user_id, clean_text):
                    await event.reply("🎉 آفرین! جواب درست بود ✅")
                    return
            except Exception as e:
                self.logger.log_error(f"خطای بررسی جواب چیستان: {e}")

"""

if "if check_answer(chat_id, user_id, clean_text)" in s:
    print("✅ قبلا اضافه شده")
elif marker in s:
    s = s.replace(marker, insert + marker, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ بررسی جواب چیستان اضافه شد")
else:
    print("❌ محل چیستان پیدا نشد")
