from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

t=t.replace(
'            print("history error:", e)\n            bot.logger.log_error(f\'خطای تاریخچه: {e}\')',
'''            print("history error:", str(e) if "e" in locals() else "unknown")
            bot.logger.log_error(f"خطای تاریخچه: {str(e) if 'e' in locals() else 'unknown'}")'''
)

p.write_text(t,encoding="utf-8")
print("✅ fixed")
