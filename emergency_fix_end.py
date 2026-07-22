from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

shutil.copy(p, "handlers/message_handler_before_emergency_fix.py")

lines = p.read_text(encoding="utf-8").splitlines()

# حذف بخش خراب از if is_spam تا انتهای فایل
start = None
for i,l in enumerate(lines):
    if l.strip() == "if is_spam:":
        start = i
        break

if start is None:
    raise Exception("if is_spam پیدا نشد")

# جایگزینی با پایان سالم
new_end = '''
        if is_spam:
            from modules.user_map import save_user

            save_user(chat_id, username, user_id)

            count = bot.tracker.increment(chat_id, user_id)
            threshold = bot.config_manager.get("spam_threshold", 3)

            try:
                bot.logger.log_deleted_message(
                    user_id=user_id,
                    username=username,
                    group_id=chat_id,
                    group_title=chat_title,
                    original_text=message_text,
                    reason=reason,
                    message_id=event.message.id
                )

                if bot.config_manager.get("delete_spam", True):
                    await bot.admin_actions.delete_message(chat_id, event=event)

                if count <= 5:
                    await bot.admin_actions.send_warning(
                        chat_id=chat_id,
                        username=username,
                        reason=reason,
                        count=count,
                        threshold=threshold,
                        reply_to=None
                    )

                if bot.tracker.should_punish(chat_id, user_id):
                    await bot.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

            except Exception as e:
                bot.logger.log_error(f"خطا در مجازات اسپم: {e}")

        return
'''

# چون انتهای تابع خراب شده، کل ادامه را می‌بریم
lines = lines[:start] + new_end.splitlines()

p.write_text("\n".join(lines), encoding="utf-8")

print("✅ انتهای تابع بازسازی شد")
