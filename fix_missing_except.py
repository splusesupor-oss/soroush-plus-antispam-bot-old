from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

# خط 1328 اشتباه داخل try است، تبدیلش کن
for i,l in enumerate(lines):
    if 'print("خطای تشخیص فوروارد:", e)' in l:
        lines[i] = '        except Exception as e:'
        lines.insert(i+1, '            print("خطای تشخیص فوروارد:", e)')
        break

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
