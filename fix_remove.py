from pathlib import Path

p = Path("modules/banned_storage.py")
text = p.read_text(encoding="utf-8")

start = text.index("def remove_banned(")
end = text.index("def is_banned(", start)

new = '''def remove_banned(group_id, username):
    data = load_banned()
    gid = str(group_id)

    if gid not in data:
        return False

    target = str(username).lower()

    for item in list(data[gid]):
        if str(item).lower() == target:
            data[gid].remove(item)
            save_banned(data)
            return True

    return False


'''

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ remove_banned fixed")
