from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("                entities = []")
end = s.find("                await event.reply(", start)

if start == -1 or end == -1:
    raise SystemExit("section not found")

new = '''                entities = []

                def u16(x):
                    return len(x.encode("utf-16-le")) // 2

                for word in [
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
                ]:
                    pos = help_text.find(word)
                    if pos != -1:
                        entities.append(
                            MessageEntityBold(
                                offset=u16(help_text[:pos]),
                                length=u16(word)
                            )
                        )

                for word in ["پاک", "سکوت", "اخراج", "آزاد"]:
                    pos = help_text.rfind(word)
                    if pos != -1:
                        entities.append(
                            MessageEntityBlockquote(
                                offset=u16(help_text[:pos]),
                                length=u16(word)
                            )
                        )

'''

s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8")
