"""ذخیره‌سازی سازگارِ کاربران بن‌شده به‌صورت دائمی برای هر گروه."""
import json
from pathlib import Path


FILE = Path("config/banned_users.json")


def load_banned():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_banned(data):
    FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _entry_matches(entry, user_id=None, username=None):
    identifiers = set()
    if user_id is not None:
        identifiers.add(str(user_id).lower())
    if username:
        identifiers.add(str(username).replace("@", "").lower())

    if isinstance(entry, dict):
        values = [entry.get("user_id"), entry.get("username")]
    else:
        values = [entry]

    return any(
        value is not None and str(value).replace("@", "").lower() in identifiers
        for value in values
    )


def add_banned(group_id, user_id, username=None, display_name=None, reason=""):
    """کاربر را با شناسه پایدار و اطلاعات نمایشی در ذخیرهٔ موجود ثبت می‌کند."""
    data = load_banned()
    gid = str(group_id)
    entries = data.setdefault(gid, [])
    record = {
        "user_id": str(user_id),
        "username": username or None,
        "display_name": display_name or None,
        "reason": reason or "بن دائمی",
    }

    for index, entry in enumerate(entries):
        if _entry_matches(entry, user_id, username):
            entries[index] = record
            save_banned(data)
            return

    entries.append(record)
    save_banned(data)


def remove_banned(group_id, user_id=None, username=None):
    """تمام رکوردهای منطبق با شناسه و نام کاربر را از فایل حذف می‌کند."""
    data = load_banned()
    gid = str(group_id)
    if gid not in data:
        return 0

    original_length = len(data[gid])
    data[gid] = [
        entry for entry in data[gid]
        if not _entry_matches(entry, user_id, username)
    ]
    removed_count = original_length - len(data[gid])
    if removed_count:
        save_banned(data)

    return removed_count


def is_banned(group_id, user_id, username=None, data=None):
    """وضعیت بن را با دادهٔ تازهٔ فایل یا دادهٔ صریحِ داده‌شده بررسی می‌کند."""
    if data is None:
        data = load_banned()
    for entry in data.get(str(group_id), []):
        if _entry_matches(entry, user_id, username):
            return True
    return False
