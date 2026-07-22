#!/data/data/com.termux/files/usr/bin/bash

cp main.py main_before_auto_help_fix.py

python3 - <<'PY'
from pathlib import Path
import re
import shutil

p = Path("main.py")
text = p.read_text(encoding="utf-8")

old = text

# پیدا کردن بخش entities بعد از help_text
start = text.find("                entities = []")
end = text.find("                event.reply", start)

if start == -1:
    raise SystemExit("بخش entities پیدا نشد")

if end == -1:
    end = text.find("\n\n", start)

new = r'''                entities = []

                def utf16_len(s):
                    return len(s.encode("utf-16-le")) // 2

                # Bold عنوان‌ها
                bold_words = [
                    "💬 پاسخ‌های ساده:",
                    "😂 جک:",
                    "🎯 بازی جرعت حقیقت:",
                    "✍️ ساخت فونت:",
                    "🛡️ امنیت گروه:",
                    "👑 دستورات ادمین‌ها:",
                    "🗑️ حذف پیام:",
                    "🔇 سکوت کاربر:",
                    "🚪 اخراج کاربر:",
                    "♻️ آزاد کردن کاربر:"
                ]

                for w in bold_words:
                    pos = help_text.find(w)
                    if pos != -1:
                        entities.append({
                            "type": "bold",
                            "offset": utf16_len(help_text[:pos]),
                            "length": utf16_len(w)
                        })

                # Blockquote فقط دستورات
                for w in ["پاک", "سکوت", "اخراج", "آزاد"]:
                    pos = help_text.rfind(w)
                    if pos != -1:
                        entities.append({
                            "type": "blockquote",
                            "offset": utf16_len(help_text[:pos]),
                            "length": utf16_len(w)
                        })

'''

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")

PY

python3 -m py_compile main.py

if [ $? -ne 0 ]; then
    echo "ERROR - restore backup"
    cp main_before_auto_help_fix.py main.py
    exit 1
fi

echo "OK - help formatting fixed"
