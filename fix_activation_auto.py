from pathlib import Path
import shutil

target = Path("handlers/message_handler.py")
source = Path("claude_files/message_handler.py")

if not target.exists():
    print("❌ target not found")
    exit()

if not source.exists():
    print("❌ source not found")
    exit()

text = target.read_text(encoding="utf-8")
src = source.read_text(encoding="utf-8")

start = src.find("# فعال و غیرفعال کردن گروه توسط مالک اصلی")
if start == -1:
    print("❌ activation block not found")
    exit()

end = src.find('if clean_text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]', start)
if end == -1:
    print("❌ activation end not found")
    exit()

block = src[start:end]

if "activate_group(gid, title)" in text:
    print("⚠️ activation already exists")
else:
    backup = target.with_name("message_handler.before_activation_restore.py")
    shutil.copy(target, backup)

    pos = text.find("async def handle_new_message")
    if pos == -1:
        pos = len(text)

    text = text[:pos] + "\n" + block + "\n" + text[pos:]

    target.write_text(text, encoding="utf-8")

    print("✅ activation restored")
    print("backup:", backup)
