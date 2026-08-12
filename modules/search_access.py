"""Persistent per-group Google Search access, allow-list, and daily quota state."""
import json
import logging
from pathlib import Path

from modules.group_id import normalize_group_id
from modules.user_display import format_user
from modules.time_utils import now_local

FILE = Path(__file__).resolve().parent.parent / "config" / "search_access.json"
DAILY_LIMIT = 27


_LEGACY_FILE = Path(__file__).resolve().parent.parent / "config" / "ai_groups.json"


def _merge_legacy(data):
    """Merge old AI-named records even if new storage already exists."""
    if not _LEGACY_FILE.exists():
        return data, False
    try:
        legacy = json.loads(_LEGACY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data, False
    if not isinstance(legacy, dict):
        return data, False
    changed = False
    for group_key, old_group in legacy.items():
        if not isinstance(old_group, dict):
            continue
        target = data.setdefault(group_key, {"enabled": False, "allowed": {}, "usage": {}})
        if old_group.get("enabled") and not target.get("enabled"):
            target["enabled"] = True; changed = True
        for bucket in ("allowed", "usage"):
            old_bucket = old_group.get(bucket) or {}
            target_bucket = target.setdefault(bucket, {})
            for key, value in old_bucket.items():
                if key not in target_bucket:
                    target_bucket[key] = value; changed = True
    return data, changed


def _load():
    try:
        if FILE.exists():
            data = json.loads(FILE.read_text(encoding="utf-8"))
            data = data if isinstance(data, dict) else {}
        else:
            data = {}
        data, merged = _merge_legacy(data)
        if merged:
            _save(data)
            logging.getLogger("SoroushAntiSpam").info(
                f"SEARCH ACCESS MIGRATION storage_path={FILE} legacy_path={_LEGACY_FILE}"
            )
        return data
    except (OSError, ValueError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(chat_id):
    return normalize_group_id(chat_id)


def _log_save(chat_id, user_id=None, enabled=None, allowed=None):
    logging.getLogger("SoroushAntiSpam").info(
        "SEARCH ACCESS SAVE "
        f"chat_id={chat_id} canonical_chat_id={_key(chat_id)} "
        f"user_id={user_id if user_id is not None else 'none'} "
        f"enabled={enabled} allowed={allowed} storage_path={FILE}"
    )


def _log_load(chat_id, user_id, enabled, allowed):
    logging.getLogger("SoroushAntiSpam").info(
        "SEARCH ACCESS LOAD "
        f"chat_id={chat_id} canonical_chat_id={_key(chat_id)} "
        f"user_id={user_id} enabled={enabled} allowed={allowed} "
        f"storage_path={FILE}"
    )


def _group(data, chat_id, create=False):
    key = _key(chat_id)
    if create:
        return data.setdefault(key, {"enabled": False, "allowed": {}, "usage": {}})
    group = data.get(key)
    return group if isinstance(group, dict) else None


def access_state(chat_id, user_id):
    """Single authoritative enabled/allowed read used by Google Search."""
    group = _group(_load(), chat_id)
    enabled = bool(group and group.get("enabled"))
    allowed = bool(enabled and str(user_id) in group.get("allowed", {}))
    _log_load(chat_id, user_id, enabled, allowed)
    return enabled, allowed


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
    _log_save(chat_id, enabled=group["enabled"], allowed=None)
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
    _log_save(chat_id, user_id=user_id, enabled=bool(group.get("enabled")), allowed=True)
    return True


def disallow(chat_id, user_id):
    data = _load()
    group = _group(data, chat_id)
    if not group or str(user_id) not in group.get("allowed", {}):
        return False
    del group["allowed"][str(user_id)]
    _save(data)
    _log_save(chat_id, user_id=user_id, enabled=bool(group.get("enabled")), allowed=False)
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
    # The final allowed request is served, then the user is informed once that the
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
