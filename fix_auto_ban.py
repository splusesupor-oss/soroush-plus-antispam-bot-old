from pathlib import Path
import shutil
import re

p = Path("handlers/message_handler.py")
if not p.exists():
    print("❌ handlers/message_handler.py پیدا نشد")
    raise SystemExit

bak = p.with_suffix(".py.bak_autoban")
shutil.copy2(p, bak)

text = p.read_text(encoding="utf-8")

pattern = re.compile(
    r'count\s*=\s*user_tracker\.increment\(chat_id,\s*user\.id\).*?await event\.reply\([\s\S]*?count}/4"\s*\)',
    re.MULTILINE
)

replacement = '''count = user_tracker.increment(chat_id, user.id)

if count >= 4:
    try:
        await bot.admin_actions.ban_user(chat_id, user.id)
    except Exception:
        pass

    user_tracker.reset_count(chat_id, user.id)

    await event.reply(
        f"🚫 کاربر @{username} بعد از ۴ اخطار بن شد."
    )
    return

await event.reply(
    f"⚠️ کاربر @{username} اخطار دریافت کرد.\\n"
    f"تعداد اخطار: {count}/4"
)'''

new_text, n = pattern.subn(replacement, text, count=1)

if n == 0:
    print("❌ بلوک اخطار پیدا نشد، تغییری انجام نشد.")
    print("📦 بکاپ:", bak)
    raise SystemExit

p.write_text(new_text, encoding="utf-8")
print("✅ اصلاح شد.")
print("📦 بکاپ:", bak)
