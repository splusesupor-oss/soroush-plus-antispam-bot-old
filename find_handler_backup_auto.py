from pathlib import Path
import re

files = list(Path(".").rglob("*.py"))

for f in files:
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "async def handle_new_message" in text:
            print("FOUND:", f)
            m = re.search(r"async def handle_new_message\(.*", text, re.S)
            if m:
                Path("handlers/handle_new_message_restore.txt").write_text(
                    m.group(0),
                    encoding="utf-8"
                )
                print("SAVED: handlers/handle_new_message_restore.txt")
                break
    except:
        pass
else:
    print("❌ no backup found")
