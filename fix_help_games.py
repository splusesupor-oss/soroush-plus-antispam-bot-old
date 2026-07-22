import shutil
from datetime import datetime

FILE="test_main.py"

backup = FILE + ".bak_help_" + datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE, backup)

with open(FILE, "r", encoding="utf-8") as f:
    text = f.read()

old = """                    "🎯 بازی جرعت حقیقت:\\n"
                    "جرعت → یک جرعت تصادفی دریافت کنید\\n"
                    "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"
"""

new = """                    "🎮 برای دریافت بازی ها:\\n"
                    "لیست بازی\\n\\n"

                    "🎮 لیست بازی ها:\\n\\n"
                    "**🧩 چیستان**\\n"
                    "یک چیستان با فرصت کم\\n\\n"

                    "**🎯 جرعت - حقیقت**\\n"
                    "یک سوال جرعت یا حقیقت تصادفی\\n\\n"

                    "**🪁 جک**\\n"
                    "یک جک خنده دار تصادفی\\n\\n"

                    "**✒️ جای خالی**\\n"
                    "۳۰ ثانیه برای جواب دادن جای خالی\\n\\n"
"""

if old not in text:
    print("بخش قدیمی پیدا نشد")
    print("BACKUP:", backup)
    exit()

text = text.replace(old, new)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("HELP GAMES UPDATED")
print("BACKUP:", backup)
