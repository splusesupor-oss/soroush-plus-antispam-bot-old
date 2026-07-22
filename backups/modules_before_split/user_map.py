import json
from pathlib import Path

FILE = Path("logs/user_map.json")


def load_map():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except:
        return {}


def save_map(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_user(group_id, username, user_id):
    if not username:
        return

    data = load_map()

    gid = str(group_id)
    uname = username.replace("@", "").lower()

    if gid not in data:
        data[gid] = {}

    data[gid][uname] = str(user_id)

    save_map(data)


def find_user(username):
    username = username.replace("@", "").lower()

    data = load_map()

    for gid, users in data.items():
        if username in users:
            return int(gid), int(users[username])

    return None, None
