from pathlib import Path

p=Path("modules/banned_storage.py")
text=p.read_text(encoding="utf-8")

start=text.index("def remove_banned(")
end=text.index("def is_banned(", start)

new='''def remove_banned(group_id, user_id):
    data = load_banned()
    gid = str(group_id)
    uid = str(user_id)

    if gid not in data:
        return False

    old = len(data[gid])

    data[gid] = [
        x for x in data[gid]
        if str(x) != uid
    ]

    save_banned(data)

    return len(data[gid]) != old


'''

text=text[:start]+new+text[end:]
p.write_text(text,encoding="utf-8")

print("✅ remove_banned fixed")
