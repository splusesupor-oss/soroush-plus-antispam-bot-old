"""مهاجرت یک‌باره و بدون حذف داده برای کلیدهای گروهی قدیمی SPlusthon."""
import json
from pathlib import Path

from modules.group_id import merge_unique, normalize_group_id


ROOT = Path(__file__).resolve().parent.parent


def _load(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_group_record(current, incoming):
    current = dict(current) if isinstance(current, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    # یک گروه اگر در هر رکورد قدیمی فعال بوده، فعال باقی می‌ماند.
    current["active"] = bool(current.get("active", False) or incoming.get("active", False))
    for key, value in incoming.items():
        if key not in current or current[key] in (None, ""):
            current[key] = value
    return current


def _merge_list(current, incoming):
    return merge_unique(current if isinstance(current, list) else [], incoming if isinstance(incoming, list) else [])


def _merge_flag(current, incoming):
    # False یک انتخاب صریح برای خاموش‌بودن فیلتر است و نباید گم شود.
    return bool(current) and bool(incoming)


def _merge_mapping(current, incoming):
    current = dict(current) if isinstance(current, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    for key, value in incoming.items():
        if key not in current:
            current[key] = value
        elif isinstance(current[key], dict) and isinstance(value, dict):
            current[key] = _merge_mapping(current[key], value)
        elif isinstance(current[key], list) and isinstance(value, list):
            current[key] = _merge_list(current[key], value)
    return current


def _merge_counters(current, incoming):
    """شمارنده‌های دو کلید هم‌ارز را بدون از دست‌دادن مقدار ادغام می‌کند."""
    current = dict(current) if isinstance(current, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    for key, value in incoming.items():
        if key not in current:
            current[key] = value
        elif isinstance(current[key], dict) and isinstance(value, dict):
            current[key] = _merge_counters(current[key], value)
        elif isinstance(current[key], (int, float)) and isinstance(value, (int, float)):
            current[key] += value
        elif isinstance(current[key], list) and isinstance(value, list):
            current[key] = _merge_list(current[key], value)
    return current


def _migrate_file(relative_path, merger):
    path = ROOT / relative_path
    data = _load(path)
    migrated = {}
    changed = False
    for old_key, value in data.items():
        new_key = normalize_group_id(old_key)
        changed = changed or new_key != str(old_key)
        if new_key in migrated:
            migrated[new_key] = merger(migrated[new_key], value)
            changed = True
        else:
            migrated[new_key] = value
    if changed:
        _save(path, migrated)
    return changed


def migrate_all_group_storage():
    """شناسه‌های کانالی را در تمام JSONهای فعال به کلید سازگار تبدیل می‌کند."""
    migrations = (
        ("config/groups.json", _merge_group_record),
        ("config/admins.json", _merge_list),
        ("config/group_words.json", _merge_list),
        ("config/group_banned_words.json", _merge_flag),
        ("config/banned_users.json", _merge_list),
        ("logs/group_stats.json", _merge_counters),
        ("logs/spam_counts.json", _merge_counters),
        ("logs/user_map.json", _merge_mapping),
        ("config/user_activity.json", _merge_mapping),
    )
    return [path for path, merger in migrations if _migrate_file(path, merger)]
