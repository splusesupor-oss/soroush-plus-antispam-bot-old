from pathlib import Path
import re

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

pattern = r'if ids:\s*for i in range\(0, len\(ids\), \d+\):\s*batch = ids\[i:i\+\d+\]'

replacement = '''if ids:
                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]'''

new_text, count = re.subn(pattern, replacement, text)

if count:
    p.write_text(new_text, encoding="utf-8")
    print("✅ حذف تاریخچه روی 100 تایی تنظیم شد")
else:
    print("❌ بخش حذف پیدا نشد")

