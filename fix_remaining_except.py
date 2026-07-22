from pathlib import Path
import shutil

file=Path("handlers/message_handler.py")

shutil.copy(file,"handlers/message_handler.py.before_remaining_except")

lines=file.read_text(encoding="utf-8").splitlines()

out=[]
i=0

while i < len(lines):

    line=lines[i]

    # پیدا کردن log_error هایی که بعد از try ناقص افتاده اند
    if "bot.logger.log_error" in line:

        # اگر خط قبلش except نیست و داخل try نیست
        prev = lines[i-1].strip() if i>0 else ""

        if not prev.startswith("except"):

            space=len(line)-len(line.lstrip())

            print("🔧 adding except before",i+1)

            out.append(" "* (space-4) +"except Exception as e:")
            out.append(line)
            i+=1
            continue

    out.append(line)
    i+=1


file.write_text(
    "\n".join(out),
    encoding="utf-8"
)

print("✅ remaining except repaired")

