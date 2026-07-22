import json
from pathlib import Path

FILE = Path("config/admins.json")

def load_admins():
    if not FILE.exists():
        return {}

    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except:
        return {}

def save_admins(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def add_admin(group_id, username):
    data = load_admins()

    gid = str(group_id)
    username = username.replace("@", "")

    if gid not in data:
        data[gid] = []

    if username not in data[gid]:
        data[gid].append(username)

    save_admins(data)
    return True

def is_admin(group_id, username):
    data = load_admins()

    if not username:
        return False

    username = username.replace("@", "")

    return username in data.get(str(group_id), [])

def remove_admin(group_id, username):
    data = load_admins()
    gid = str(group_id)
    username = username.replace("@", "")

    if gid in data and username in data[gid]:
        data[gid].remove(username)
        save_admins(data)
        return True

    return False

def remove_admin(group_id, username):
    data = load_admins()
    gid = str(group_id)
    username = username.replace("@", "")

    if gid in data and username in data[gid]:
        data[gid].remove(username)
        save_admins(data)
        return True

    return False
