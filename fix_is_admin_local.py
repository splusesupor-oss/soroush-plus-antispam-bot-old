from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

old = "from modules.admin_storage import is_admin"

# فقط ایمپورت‌های تکراری داخل بدنه را حذف می‌کند
lines = s.splitlines()
out = []
seen_top = False

for i, line in enumerate(lines):
    if line.strip() == old:
        if not seen_top and i < 30:
            out.append(line)
            seen_top = True
        else:
            print("REMOVE:", i+1, line)
            continue
    else:
        out.append(line)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ ایمپورت محلی is_admin اصلاح شد")
