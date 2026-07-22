from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out=[]

for line in lines:
    s=line.strip()

    # except هایی که اشتباه رفته اند داخل try
    if s == "except Exception as e:":
        indent=len(line)-len(line.lstrip())

        # اگر indent آن بیشتر از 8 بود، اصلاح کن
        if indent >= 8:
            line="            except Exception as e:"

    # logger های بعد از except خراب
    out.append(line)

p.write_text("\n".join(out), encoding="utf-8")

print("✅ except indentation fixed")
