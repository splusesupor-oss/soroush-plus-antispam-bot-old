from pathlib import Path
import shutil

target = Path("handlers/message_handler.py")
backup = target.with_name("message_handler.before_activation_indent_fix.py")

shutil.copy(target, backup)

lines = target.read_text(encoding="utf-8").splitlines()

new = []
skip = False
depth = 0

for line in lines:
    if '# فعال و غیرفعال کردن گروه توسط مالک اصلی' in line:
        skip = True
        continue

    if skip:
        if 'if clean_text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]' in line:
            skip = False
            new.append(line)
        continue

    new.append(line)

target.write_text("\n".join(new)+"\n", encoding="utf-8")

print("✅ broken activation block removed")
print("backup:", backup)
