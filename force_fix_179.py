from pathlib import Path
import shutil

file=Path("handlers/message_handler.py")

shutil.copy(file,"handlers/message_handler.py.before_force179")

lines=file.read_text(encoding="utf-8").splitlines()

out=[]

fixed=False

for line in lines:

    if line.strip()=="# جستجوی وب" and not fixed:

        out.append("        except Exception as e:")
        out.append("            bot.logger.log_error(f'خطای تاریخچه: {e}')")
        out.append("            pass")
        out.append("")
        fixed=True

    out.append(line)


file.write_text(
    "\n".join(out),
    encoding="utf-8"
)

print("✅ except before search inserted")

