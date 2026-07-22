from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

line = "from modules.riddles import new_riddle, check_answer, get_answer\n"

if "from modules.riddles import" not in s:
    pos = s.find("\n")
    s = s[:pos+1] + line + s[pos+1:]
    print("✅ ایمپورت چیستان اضافه شد")
elif "check_answer" not in s.split("from modules.riddles import",1)[1].split("\n",1)[0]:
    s = s.replace(
        s[s.find("from modules.riddles import"):s.find("\n", s.find("from modules.riddles import"))],
        line.strip()
    )
    print("✅ check_answer به ایمپورت اضافه شد")
else:
    print("ℹ️ قبلا وجود داشت")

p.write_text(s, encoding="utf-8")
