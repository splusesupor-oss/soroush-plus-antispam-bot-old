from pathlib import Path

for b in Path("handlers").glob("message_handler*.py*"):
    try:
        t=b.read_text(encoding="utf-8")
        if (
            'if clean_text.strip() in ["راهنما"' in t
            and "except Exception" in t
            and "if clean_text.startswith" in t
        ):
            print(b)
    except:
        pass
