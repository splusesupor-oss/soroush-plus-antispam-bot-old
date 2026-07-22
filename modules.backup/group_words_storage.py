import json
from pathlib import Path

FILE = Path("config/group_words.json")


def load_words():
    if not FILE.exists():
        return {}

    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except:
        return {}


def save_words(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_word(group_id, word):
    data = load_words()
    gid = str(group_id)

    if gid not in data:
        data[gid] = []

    word = word.strip()

    if word and word not in data[gid]:
        data[gid].append(word)
        save_words(data)
        return True

    return False


def remove_word(group_id, word):
    data = load_words()
    gid = str(group_id)

    if gid in data and word in data[gid]:
        data[gid].remove(word)
        save_words(data)
        return True

    return False


def get_words(group_id):
    data = load_words()
    return data.get(str(group_id), [])
