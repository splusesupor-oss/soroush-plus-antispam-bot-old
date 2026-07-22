#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_spam_fix_$(date +%s).bak

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("            # ضد اسپم پیام‌های پشت سرهم")
end = s.find("            # حذف پیام های فوروارد شده")

if start != -1 and end != -1:
    new_block = r'''            # ضد فلود جدید - فقط پیام چندخطی تکراری
            try:
                import re

                lines = [
                    x.strip()
                    for x in message_text.splitlines()
                    if x.strip()
                ]

                repeat_lines = False

                if len(lines) >= 5:
                    unique = set(lines)

                    for line in unique:
                        if lines.count(line) >= 5:
                            repeat_lines = True
                            break

                if repeat_lines:
                    await self.admin_actions.delete_message(
                        chat_id,
                        event=event
                    )

                    await self.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                    return

            except Exception as e:
                self.logger.log_error(
                    f"خطای ضد تکرار چندخطی: {e}"
                )

'''
    s = s[:start] + new_block + s[end:]

p.write_text(s, encoding="utf-8")

print("✅ Spam logic fixed")
PY

echo "✅ Backup created"
echo "Restart bot now"
