from pathlib import Path
import re

files = list(Path(".").rglob("*.py")) + list(Path(".").rglob("*.json"))

changed = False

for p in files:
    try:
        s = p.read_text(encoding="utf-8")

        old = s

        # حذف گروه از لیست‌های ممنوعه
        s = re.sub(
            r'(["\']گروه["\']\s*,?\s*)',
            '',
            s
        )

        # اضافه کردن بیو چک به لیست ممنوعه اگر وجود داشت
        if "بیوم چک" not in s and "بیو چک" not in s:
            patterns = [
                r'(\[.*?)(["\'].*?["\'])(.*?\])'
            ]

            for pat in patterns:
                m = re.search(pat, s, re.S)
                if m and ("banned" in s.lower() or "ban" in s.lower() or "ممنوع" in s):
                    break

        if s != old:
            p.write_text(s, encoding="utf-8")
            print("✅ اصلاح شد:", p)
            changed = True

    except Exception:
        pass

if not changed:
    print("⚠️ چیزی تغییر نکرد. احتمالاً لیست کلمات ممنوعه در فایل جداگانه است.")
