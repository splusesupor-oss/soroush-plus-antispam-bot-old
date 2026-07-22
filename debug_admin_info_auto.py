from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

start=text.find("async def get_activation_admin_info")
end=text.find("\nasync def ", start+10)

if end==-1:
    end=len(text)

func=text[start:end]

print(func)
