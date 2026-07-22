from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

starts = [i for i,l in enumerate(lines)
          if 'if clean_text in ["فعال سازی", "غیر فعال"]:' in l]

if len(starts) < 2:
    print("second block not found")
    raise SystemExit

start = starts[1]

end = None
for i in range(start + 1, len(lines)):
    if "# ثبت ادمین" in lines[i]:
        end = i
        break

if end is None:
    print("end marker not found")
    raise SystemExit

backup = p.with_suffix(".before_remove_second_activation.py")
backup.write_text("\n".join(lines) + "\n", encoding="utf-8")

del lines[start:end]

p.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("DONE")
print("removed:", start + 1, "to", end)
print("backup:", backup)
