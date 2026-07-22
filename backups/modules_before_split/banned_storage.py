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

def add_banned(group_id, user_id):
    data = load_banned()
    gid = str(group_id)

    if gid not in data:
        data[gid] = []

    uid = str(user_id)

    if uid not in [str(x) for x in data[gid]]:
        data[gid].append(uid)

    save_banned(data)

def remove_banned(group_id, user_id):
    data = load_banned()
    gid = str(group_id)
    uid = str(user_id)

    if gid in data:
        for x in list(data[gid]):
            if str(x) == uid:
                data[gid].remove(x)
                save_banned(data)
                return True

    return False


def is_banned(group_id, user_id, username=None):
    data = load_banned()
    gid = str(group_id)

    if gid not in data:
        return False

    uid = str(user_id)

    for x in data[gid]:
        if str(x) == uid:
            return True

        if username and str(x).lower() == str(username).lower():
            return True

    return False
