from pathlib import Path

f = Path("handlers/message_handler.py")
text = f.read_text(encoding="utf-8")

old = '''            await event.reply(games_text)
            return'''

new = '''            entities = []

            def u16(x):
                return len(x.encode("utf-16-le")) // 2

            for word in [
                "🎮 لیست بازی ها:",
                "🧩 چیستان",
                "🎯 جرعت - حقیقت",
                "😂 جک",
                "✍️ جای خالی"
            ]:
                pos = games_text.find(word)
                if pos != -1:
                    entities.append(
                        MessageEntityBold(
                            offset=u16(games_text[:pos]),
                            length=u16(word)
                        )
                    )

            await event.reply(
                games_text,
                formatting_entities=entities
            )
            return'''

if old not in text:
    print("NOT FOUND")
else:
    text=text.replace(old,new,1)
    f.write_text(text,encoding="utf-8")
    print("DONE")
