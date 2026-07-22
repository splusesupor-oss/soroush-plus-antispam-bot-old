from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
"await self.check_group_word_commands(",
"await bot.check_group_word_commands("
)

text = text.replace(
"await self.handle_admin_commands(",
"await bot.handle_admin_commands("
)

text = text.replace(
"hasattr(self, \"flood_messages\")",
"hasattr(bot, \"flood_messages\")"
)

p.write_text(text, encoding="utf-8")
print("✅ self fixed")
