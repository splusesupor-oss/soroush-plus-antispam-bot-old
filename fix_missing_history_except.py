from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out=[]
fixed=False

for i,l in enumerate(lines):
    if l.strip() == "# بررسی کلمات فیلتر شده گروه":
        if not fixed:
            out.append("                except Exception as ex:")
            out.append("                    print('history delete error:', ex)")
            out.append("")
            fixed=True

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ missing except added" if fixed else "❌ marker not found")
