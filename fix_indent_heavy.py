from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i in range(1330, 1375):
    if i < len(lines):
        if lines[i].strip():
            lines[i] = " " * 32 + lines[i].lstrip()

# except اصلی بعد از تکرار باید 28 فاصله باشد
for i,l in enumerate(lines):
    if "except Exception as e:" in l and i > 1350 and i < 1380:
        lines[i] = "                            except Exception as e:"

p.write_text("\n".join(lines), encoding="utf-8")
print("OK")
