import ast
import json
from pathlib import Path

print("🔍 شروع بررسی ربات...\n")

files = [
    "main.py",
    "modules/spam_detector.py",
    "modules/admin_actions.py",
    "modules/config_manager.py"
]

for f in files:
    p = Path(f)
    if not p.exists():
        print("❌ پیدا نشد:", f)
        continue
    try:
        ast.parse(p.read_text(encoding="utf-8"))
        print("✅ کد سالم:", f)
    except Exception as e:
        print("❌ خطای سینتکس:", f, e)

print("\n⚙️ بررسی تنظیمات...")

try:
    config = json.loads(Path("config/config.json").read_text(encoding="utf-8"))

    for k in ["delete_spam","send_warning","spam_threshold","action_on_threshold"]:
        print(k, "=", config.get(k,"وجود ندارد"))

except Exception as e:
    print("❌ خطای config:", e)


print("\n🚫 تست کلمات ممنوعه...")

try:
    from modules.config_manager import ConfigManager
    from modules.spam_detector import SpamDetector

    c = ConfigManager()
    d = SpamDetector(c)

    tests = ["خرید","تبلیغ","لینک","پیوی","جوین"]

    print("تعداد کلمات ممنوعه:", len(c.banned_words))

    for t in tests:
        result = d.is_spam(t)
        print(t, "=>", result)

except Exception as e:
    print("❌ خطای تست ضداسپم:", e)


print("\n✅ بررسی تمام شد")
