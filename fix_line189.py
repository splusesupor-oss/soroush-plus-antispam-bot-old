from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(len(lines)):
    if 'except Exception as err:' in lines[i] and i+1 < len(lines) and 'BAN ERROR' in lines[i+1]:
        lines[i] = "                  except Exception as err:"
        break

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("✅ indent fixed")
