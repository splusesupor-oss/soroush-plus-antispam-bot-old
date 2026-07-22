from pathlib import Path
import json,re

print("🔎 بررسی واقعی شروع شد\n")

main=Path("main.py").read_text(encoding="utf-8",errors="ignore")

# 1
if "add_banned(" in main:
    print("✅ add_banned وجود دارد")
else:
    print("❌ add_banned پیدا نشد")

# 2
m=re.search(r"add_banned\((.*?)\)",main,re.S)
if m:
    print("📌 چیزی که ذخیره می‌شود:")
    print(m.group(1).strip())

# 3
if "event.user_joined" in main and "is_banned" in main:
    print("✅ چک ورود کاربر بن شده وجود دارد")
else:
    print("❌ چک ورود ناقص است")

# 4
try:
    data=json.loads(Path("config/banned_users.json").read_text())

    ids=0
    names=0

    for g,u in data.items():
        for x in u:
            if str(x).isdigit():
                ids+=1
            else:
                names+=1

    print(f"\n📊 ذخیره بن:")
    print("ID:",ids)
    print("Username:",names)

    if ids and names:
        print("⚠️ مشکل: روش ذخیره دوگانه است")

except Exception as e:
    print("خطای فایل بن:",e)


# 5
if "kick_participant" in main:
    print("✅ kick وجود دارد")
else:
    print("❌ kick پیدا نشد")


print("\nتمام")
