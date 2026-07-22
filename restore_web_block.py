from pathlib import Path

dst = Path("handlers/message_handler.py")
src = Path("handlers/message_handler.py.FINAL_SAFE")

t = dst.read_text(encoding="utf-8")
b = src.read_text(encoding="utf-8")

start = b.find("if clean_text.startswith")
end = b.find("# پاسخ خودکار", start)

if start == -1 or end == -1:
    raise SystemExit("❌ search code not found")

block = b[start:end]

if "if clean_text.startswith(\"جستجو \")" not in t:
    pos = t.find("# پاسخ خودکار پیام‌ها")
    if pos == -1:
        pos = t.find("auto_replies")

    if pos == -1:
        raise SystemExit("❌ insert point not found")

    t = t[:pos] + block + "\n\n" + t[pos:]

dst.write_text(t, encoding="utf-8")

print("✅ SEARCH FIXED")
