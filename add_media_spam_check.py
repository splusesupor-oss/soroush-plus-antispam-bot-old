from pathlib import Path

p = Path("modules/spam_detector.py")

text = p.read_text(encoding="utf-8")

add = r'''

    def check_media_spam(self, message):
        """
        تشخیص اسپم فایل و عکس
        """
        try:
            if not message:
                return False

            if getattr(message, "photo", None):
                return True

            if getattr(message, "file", None):
                filename = getattr(message.file, "name", "") or ""
                
                bad = [
                    ".exe",
                    ".apk",
                    ".zip",
                    ".rar",
                    ".scr",
                    ".bat"
                ]

                for x in bad:
                    if filename.lower().endswith(x):
                        return True

            return False

        except Exception as e:
            print("media spam check error:", e)
            return False
'''

if "def check_media_spam" not in text:
    text += add
    p.write_text(text, encoding="utf-8")
    print("✅ media spam check added")
else:
    print("already exists")
