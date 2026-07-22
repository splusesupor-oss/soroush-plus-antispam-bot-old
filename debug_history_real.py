from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

t=t.replace(
'bot.logger.log_error("خطای تاریخچه ثبت شد")',
'bot.logger.log_error("خطای تاریخچه: "+repr(__import__("sys").exc_info()[1]))'
)

p.write_text(t,encoding="utf-8")
print("✅ debug enabled")
