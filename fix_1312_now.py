from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out=[]
skip=False

for line in lines:
    if line.strip() == "except Exception as e:" and len(out)>0:
        prev = out[-1].strip()

        # درست کردن except خراب فوروارد
        if prev.startswith("return") and len(out[-1]) >= 20:
            out.append("        except Exception as e:")
            continue

    # خط خراب قبلی را حذف کن
    if line.strip() == "except Exception as e:":
        if out and out[-1].strip()=="return":
            continue

    out.append(line)

p.write_text("\n".join(out), encoding="utf-8")
print("FIXED")
