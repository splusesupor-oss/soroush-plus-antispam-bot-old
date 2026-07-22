import json
from pathlib import Path

FILE = Path("config/owner.json")

def get_owner():
    if not FILE.exists():
        return None

    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return data.get("username")
    except:
        return None

def is_owner(username):
    owner = get_owner()
    if not owner or not username:
        return False

    return username.lower().replace("@", "") == owner.lower().replace("@", "")
