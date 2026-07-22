"""ذخیره‌سازی سازگارِ کاربران بن‌شده به‌صورت دائمی برای هر گروه."""
import json
from pathlib import Path


FILE = Path(__file__).resolve().parent.parent / "config" / "banned_users.json"


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


def _normalise_identifier(value):
    if value is None:
        return None
    value = str(value).replace("@", "").strip().lower()
    return value or None


def _entry_matches(
    entry, user_id=None, username=None, display_name=None, extra_identifiers=None
):
    identifiers = {
        value for value in (
            _normalise_identifier(user_id),
            _normalise_identifier(username),
            _normalise_identifier(display_name),
            *(_normalise_identifier(value) for value in (extra_identifiers or [])),
        ) if value
    }

    if isinstance(entry, dict):
        values = [
            entry.get("user_id"),
            entry.get("username"),
            entry.get("display_name"),
            *entry.get("username_aliases", []),
        ]
    else:
        values = [entry]

    return any(
        _normalise_identifier(value) in identifiers
        for value in values
        if value is not None
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
        "username_aliases": [],
    }

    for index, entry in enumerate(entries):
        if _entry_matches(entry, user_id, username, display_name):
            if isinstance(entry, dict):
                aliases = [
                    entry.get("username"),
                    *entry.get("username_aliases", []),
                ]
                record["username_aliases"] = sorted({
                    alias for alias in aliases
                    if alias and _normalise_identifier(alias)
                    != _normalise_identifier(username)
                })
            entries[index] = record
            save_banned(data)
            return

    entries.append(record)
    save_banned(data)


def remove_banned(group_id, user_id=None, username=None, display_name=None):
    """تمام رکوردهای منطبق با شناسه، نام و لقب کاربر را از فایل حذف می‌کند."""
    data = load_banned()
    gid = str(group_id)
    if gid not in data:
        return 0

    original_length = len(data[gid])
    data[gid] = [
        entry for entry in data[gid]
        if not _entry_matches(entry, user_id, username, display_name)
    ]
    removed_count = original_length - len(data[gid])
    if removed_count:
        save_banned(data)

    return removed_count


def find_banned_records(user_id=None, username=None, display_name=None, data=None):
    """تمام رکوردهای منطبق را در همهٔ گروه‌ها، از دادهٔ تازهٔ فایل پیدا می‌کند."""
    if data is None:
        data = load_banned()

    return {
        group_id: [
            entry for entry in entries
            if isinstance(entries, list)
            and _entry_matches(entry, user_id, username, display_name)
        ]
        for group_id, entries in data.items()
        if isinstance(entries, list)
        and any(
            _entry_matches(entry, user_id, username, display_name)
            for entry in entries
        )
    }


def remove_banned_everywhere(user_id=None, username=None, display_name=None):
    """تمام رکوردهای بنِ یک کاربر را در همهٔ گروه‌های فایل حذف می‌کند."""
    data = load_banned()
    before_records = find_banned_records(
        user_id, username, display_name, data
    )
    username_aliases = {
        alias
        for entries in before_records.values()
        for entry in entries
        if isinstance(entry, dict)
        for alias in [entry.get("username"), *entry.get("username_aliases", [])]
        if alias
    }
    removed_count = 0

    for group_id, entries in data.items():
        if not isinstance(entries, list):
            continue
        remaining = [
            entry for entry in entries
            if not _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
        ]
        removed_count += len(entries) - len(remaining)
        data[group_id] = remaining

    if removed_count:
        save_banned(data)

    fresh_data = load_banned()
    remaining_records = {
        group_id: [
            entry for entry in entries
            if isinstance(entries, list)
            and _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
        ]
        for group_id, entries in fresh_data.items()
        if isinstance(entries, list)
        and any(
            _entry_matches(
                entry,
                user_id,
                username,
                display_name,
                username_aliases,
            )
            for entry in entries
        )
    }
    return removed_count, before_records, remaining_records


def get_matching_ban_records(group_id, user_id, username=None, data=None):
    """رکوردهای دقیقِ گروهی را که باعث تشخیص بن می‌شوند برمی‌گرداند."""
    if data is None:
        data = load_banned()
    return [
        entry for entry in data.get(str(group_id), [])
        if _entry_matches(entry, user_id, username)
    ]


def is_banned(group_id, user_id, username=None, data=None):
    """وضعیت بن را با دادهٔ تازهٔ فایل یا دادهٔ صریحِ داده‌شده بررسی می‌کند."""
    records = get_matching_ban_records(group_id, user_id, username, data)
    banned = bool(records)
    if banned:
        print(
            "BANNED STORAGE MATCH "
            f"user_id={user_id} username={username} group_id={group_id} "
            f"source={FILE} records={records}"
        )
    return banned
