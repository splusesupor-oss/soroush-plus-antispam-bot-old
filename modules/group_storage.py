import json
from pathlib import Path

FILE = Path("config/groups.json")

def load_groups():
    if not FILE.exists():
        return {}

    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except:
        return {}

def save_groups(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def activate_group(group_id, title):
    data = load_groups()

    data[str(group_id)] = {
        "title": title,
        "active": True
    }

    save_groups(data)

def deactivate_group(group_id, title):
    data = load_groups()

    data[str(group_id)] = {
        "title": title,
        "active": False
    }

    save_groups(data)

def is_active(group_id):
    data = load_groups()
    return data.get(str(group_id), {}).get("active", False)
