"""Persistent per-group AI access, allow-list, and daily quota state."""
import json
from pathlib import Path

from modules.group_id import normalize_group_id
from modules.user_display import format_user
from modules.time_utils import now_local

FILE = Path(__file__).resolve().parent.parent / "config" / "ai_groups.json"
DAILY_LIMIT = 50


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(chat_id):
    return normalize_group_id(chat_id)


def _group(data, chat_id, create=False):
    key = _key(chat_id)
    if create:
        return data.setdefault(key, {"enabled": False, "allowed": {}, "usage": {}})
    group = data.get(key)
    return group if isinstance(group, dict) else None


def is_enabled(chat_id):
    group = _group(_load(), chat_id)
    return bool(group and group.get("enabled"))


def set_enabled(chat_id, enabled):
    data = _load()
    group = _group(data, chat_id, create=True)
    group["enabled"] = bool(enabled)
    group.setdefault("allowed", {})
    group.setdefault("usage", {})
    _save(data)
    return group["enabled"]


def allow(chat_id, user):
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False
    data = _load()
    group = _group(data, chat_id, create=True)
    allowed = group.setdefault("allowed", {})
    allowed[str(user_id)] = {
        "username": getattr(user, "username", None),
        "display": format_user(user),
    }
    _save(data)
    return True


def disallow(chat_id, user_id):
    data = _load()
    group = _group(data, chat_id)
    if not group or str(user_id) not in group.get("allowed", {}):
        return False
    del group["allowed"][str(user_id)]
    _save(data)
    return True


def is_allowed(chat_id, user_id):
    group = _group(_load(), chat_id)
    return bool(group and str(user_id) in group.get("allowed", {}))


def _today():
    return now_local().date().isoformat()


def _usage_bucket(group, day=None):
    usage = group.setdefault("usage", {})
    day = day or _today()
    # Only today's usage matters.  Pruning makes daily reset persistent and
    # prevents the configuration file growing forever.
    for key in list(usage):
        if key != day:
            usage.pop(key, None)
    return usage.setdefault(day, {})


def reserve_request(chat_id, user_id):
    """Atomically reserve one daily request.

    Returns ``(allowed, count, send_notice)``.  The one-time notice flag is
    persisted, while membership in the allow-list is intentionally retained.
    """
    data = _load()
    group = _group(data, chat_id)
    if not group or not group.get("enabled") or str(user_id) not in group.get("allowed", {}):
        return False, 0, False
    bucket = _usage_bucket(group)
    entry = bucket.setdefault(str(user_id), {"count": 0, "notified": False})
    count = int(entry.get("count", 0))
    if count >= DAILY_LIMIT:
        send_notice = not bool(entry.get("notified"))
        entry["notified"] = True
        _save(data)
        return False, count, send_notice
    new_count = count + 1
    entry["count"] = new_count
    # The 50th request is served, then the user is informed once that the
    # next message will not reach the API until tomorrow.
    send_notice = new_count >= DAILY_LIMIT and not bool(entry.get("notified"))
    if send_notice:
        entry["notified"] = True
    _save(data)
    return True, new_count, send_notice


def allowed_users(chat_id):
    data = _load()
    group = _group(data, chat_id)
    if not group:
        return []
    before_days = set((group.get("usage") or {}).keys())
    bucket = _usage_bucket(group)
    changed = set((group.get("usage") or {}).keys()) != before_days
    rows = []
    for user_id, profile in group.get("allowed", {}).items():
        profile = profile if isinstance(profile, dict) else {}
        usage = bucket.get(str(user_id), {})
        rows.append({
            "user_id": str(user_id),
            "display": profile.get("display") or "کاربر ناشناس",
            "username": profile.get("username"),
            "count": int(usage.get("count", 0)),
        })
    if changed:
        _save(data)
    return rows


def reset_for_tests():
    _save({})
