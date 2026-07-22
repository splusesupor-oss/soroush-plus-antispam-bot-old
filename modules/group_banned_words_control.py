import json
import os

FILE = "config/group_banned_words.json"


def load():
    if not os.path.exists(FILE):
        return {}
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def enable(chat_id):
    data = load()
    data[str(chat_id)] = True
    save(data)


def disable(chat_id):
    data = load()
    data[str(chat_id)] = False
    save(data)


def is_enabled(chat_id):
    data = load()
    return data.get(str(chat_id), True)
