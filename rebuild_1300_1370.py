from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=1299
end=1370

new = r'''
        # استثنا: فوروارد کانال osine1
        try:
            if getattr(event.message, "fwd_from", None):
                fwd = event.message.fwd_from
                fwd_id = getattr(getattr(fwd, "from_id", None), "channel_id", None)
                if fwd_id == 22389465:
                    print("✅ فوروارد کانال osine1 محافظت شد")
                    return
        except Exception as e:
            print("خطای تشخیص فوروارد:", e)

        # بررسی تکرار شدید داخل یک پیام
        try:
            import re

            words = re.findall(r"\w+|[آ-ی]+", message_text.lower())
            repeat_found = False

            for w in set(words):
                if len(w) >= 3 and words.count(w) >= 8:
                    repeat_found = True
                    break

            if repeat_found:
                from modules.user_map import save_user
                save_user(chat_id, username, user_id)

                await bot.admin_actions.delete_message(
                    chat_id,
                    event=event
                )

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                await bot.admin_actions.punish_user(
                    chat_id,
                    user_id,
                    username
                )

                return

        except Exception as e:
            bot.logger.log_error(f"خطای بررسی تکرار داخلی: {e}")
'''

lines[start:end]=new.strip("\n").splitlines()

p.write_text("\n".join(lines),encoding="utf-8")
print("REBUILT")
