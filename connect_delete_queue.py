from pathlib import Path

p = Path("core/bot_working_split_ok.py")
text = p.read_text(encoding="utf-8")

imp = "from modules.security.delete_queue import process_delete\n"

if "from modules.security.delete_queue import process_delete" not in text:
    text = imp + text

target = "await self.initialize_client()\n"

insert = """
        asyncio.create_task(process_delete(self))
"""

if "create_task(process_delete(self))" not in text:
    text = text.replace(target, target + insert)

p.write_text(text, encoding="utf-8")

print("✅ delete queue connected")
