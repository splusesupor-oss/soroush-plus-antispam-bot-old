import json
from pathlib import Path

FILE = Path("config/banned_users.json")

def load_banned():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except:
        return {}

def save_banned(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def add_banned(group_id, username):
    data = load_banned()

    gid = str(group_id)

    if gid not in data:
        data[gid] = []

    if username not in data[gid]:
        data[gid].append(username)

    save_banned(data)

def remove_banned(group_id, username):
    data = load_banned()

    gid = str(group_id)

    if gid in data and username in data[gid]:
        data[gid].remove(username)
        save_banned(data)
        return True

    return False
