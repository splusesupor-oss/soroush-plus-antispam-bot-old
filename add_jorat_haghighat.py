from pathlib import Path

p = Path("modules/jorat_haghighat.py")

code = r'''
import random

JORAT = [
    "یک خاطره خنده‌دار از خودت تعریف کن 😂",
    "۵ دقیقه بدون استفاده از موبایل بمان 😄",
    "یک جمله با کلمه‌ای که بقیه انتخاب می‌کنند بساز",
    "آخرین چیزی که باعث خنده‌ات شد را بگو",
    "یک تعریف واقعی از نفر سمت راستت بکن",
    "یک آهنگ را با صدای بلند زمزمه کن 🎵",
]

HAGHIGHAT = [
    "بزرگ‌ترین ترست چیست؟",
    "آخرین باری که گریه کردی کی بود؟",
    "اگر یک آرزو داشتی چه می‌خواستی؟",
    "بدترین عادتت چیست؟",
    "تا حالا دروغ بزرگی گفته‌ای؟",
    "دوست داری چه چیزی را در خودت تغییر بدهی؟",
]

def get_jorat():
    return random.choice(JORAT)

def get_haghighat():
    return random.choice(HAGHIGHAT)
'''

p.write_text(code, encoding="utf-8")

main = Path("main.py")
text = main.read_text(encoding="utf-8")

if "jorat_haghighat" not in text:
    text = text.replace(
        "from modules",
        "from modules.jorat_haghighat import get_jorat, get_haghighat\nfrom modules"
    )

    marker = "await self.handle_new_message(event)"

    patch = '''
            if text.strip() == "جرعت":
                await event.reply("🎯 جرعت: " + get_jorat())
                return

            if text.strip() == "حقیقت":
                await event.reply("❓ حقیقت: " + get_haghighat())
                return

'''

    text = text.replace(marker, patch + marker)

    main.write_text(text, encoding="utf-8")

print("✅ بازی جرعت حقیقت اضافه شد")
