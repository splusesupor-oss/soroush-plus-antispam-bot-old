from pathlib import Path
import re

dst = Path("handlers/message_handler.py")
src = Path("handlers/message_handler.py.SAFE_NOW")

if not src.exists():
    src = Path("handlers/message_handler.py.FINAL_SAFE")

if not src.exists():
    raise SystemExit("backup not found")

main = dst.read_text(encoding="utf-8")
backup = src.read_text(encoding="utf-8")

# restore web search block
m = re.search(
    r"# جستجوی وب(.*?)# پاسخ خودکار",
    backup,
    re.S
)

if m:
    block = "# جستجوی وب" + m.group(1)

    main = re.sub(
        r"# جستجوی وب.*?# پاسخ خودکار",
        block + "\n\n# پاسخ خودکار",
        main,
        flags=re.S
    )

# restore imports
if "from modules.web_search import can_search, search_web" not in main:
    main = "from modules.web_search import can_search, search_web\n" + main

dst.write_text(main, encoding="utf-8")

print("✅ web search restored")
