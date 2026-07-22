from pathlib import Path

main = Path("handlers/message_handler.py")
backup = Path("handlers/message_handler.py.FINAL_SAFE")

if not backup.exists():
    print("❌ فایل FINAL_SAFE پیدا نشد")
    exit()

src = main.read_text(encoding="utf-8")
bak = backup.read_text(encoding="utf-8")

start = bak.find("        # جستجوی وب")
end = bak.find("        #", start + 20)

if start == -1:
    print("❌ بلاک جستجو در بکاپ پیدا نشد")
    exit()

block = bak[start:end]

if "# جستجوی وب" in src:
    print("⚠️ بلاک جستجو وجود دارد")
    exit()

insert = src.find("        # پاسخ معرفی ربات")

if insert == -1:
    print("❌ محل تزریق پیدا نشد")
    exit()

src = src[:insert] + block + "\n\n" + src[insert:]

main.write_text(src, encoding="utf-8")

print("✅ SEARCH RESTORED")
