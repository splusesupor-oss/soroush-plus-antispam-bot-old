from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

old='''participant = getattr(user, "participant", None)
            if participant:
                kind = participant.__class__.__name__'''

new='''participant = getattr(user, "participant", None)
            print("PART DEBUG:", getattr(user,"id",None), getattr(user,"username",None), type(user), type(participant), participant)
            if participant:
                kind = participant.__class__.__name__'''

if old in text:
    text=text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ debug added")
else:
    print("❌ marker not found")
