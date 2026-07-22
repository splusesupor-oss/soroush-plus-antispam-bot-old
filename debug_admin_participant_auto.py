from pathlib import Path

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

old = "participant = getattr(user, \"participant\", None)"

new = """participant = getattr(user, "participant", None)

                print("ADMIN DEBUG USER:", getattr(user,"id",None), getattr(user,"username",None))
                print("PARTICIPANT TYPE:", type(participant))
                print("PARTICIPANT DIR:", dir(participant) if participant else None)
                print("PARTICIPANT:", participant)
"""

if old not in text:
    print("❌ target not found")
    exit()

text = text.replace(old,new)

p.write_text(text,encoding="utf-8")

print("✅ debug inserted")
