from pathlib import Path
import re

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

old='bot.logger.log_error(f"خطای تاریخچه: {e}")'

if old in t:
    t=t.replace(
        old,
        'bot.logger.log_error(f"خطای تاریخچه: {str(e) if \"e\" in locals() else \"unknown\"}")'
    )
    p.write_text(t,encoding="utf-8")
    print("✅ fixed history error")
else:
    print("❌ not found")
