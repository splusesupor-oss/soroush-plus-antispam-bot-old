import os
import re

ROOT = os.getcwd()

patterns = {
    "ذخیره add_banned": r"add_banned\s*\(",
    "بررسی is_banned": r"is_banned\s*\(",
    "حذف remove_banned": r"remove_banned\s*\(",
    "ورود ChatAction": r"ChatAction|user_joined|user_added",
    "اخراج kick": r"kick_participant|kick",
    "بن واقعی edit_permissions": r"edit_permissions|EditBannedRequest|ChatBannedRights",
    "فایل ذخیره بن": r"sqlite|json|pickle|banned|storage"
}

found = {k: [] for k in patterns}

print("🔎 شروع بررسی هوشمند بن...\n")

for root, dirs, files in os.walk(ROOT):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                data = open(path, encoding="utf-8").read()

                for name, pat in patterns.items():
                    if re.search(pat, data, re.I):
                        found[name].append(path)

            except:
                pass


for name, files in found.items():
    print("━━━━━━━━━━━━━━━━")
    print("📌", name)
    if files:
        for f in files[:5]:
            print("   ✅", f)
    else:
        print("   ❌ پیدا نشد")


print("\n🧠 نتیجه‌گیری:\n")

if found["ذخیره add_banned"] and found["بررسی is_banned"]:
    print("✅ سیستم ذخیره و خواندن بن وجود دارد")

else:
    print("❌ مسیر ذخیره یا بررسی بن ناقص است")


if found["اخراج kick"] and not found["بن واقعی edit_permissions"]:
    print("⚠️ فقط kick دیده شد؛ احتمال برگشت کاربر زیاد است")

if found["ورود ChatAction"]:
    print("✅ بررسی ورود کاربر وجود دارد")
else:
    print("❌ چک ورود کاربر پیدا نشد")


print("\nتمام شد.")
