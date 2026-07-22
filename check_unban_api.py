from pathlib import Path

for f in [
    "modules/admin_actions.py",
    "modules/admin_actions.bak.py",
    "handlers/message_handler.py"
]:
    p=Path(f)
    if p.exists():
        print("\n====",f,"====")
        t=p.read_text(encoding="utf-8",errors="ignore")
        for x in ["ban_user","unban","unmute","kick_user","remove_banned"]:
            if x in t:
                print("✅",x)
