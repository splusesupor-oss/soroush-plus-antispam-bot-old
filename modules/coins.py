"""Persistent per-group coins, game wins, and daily message ranking."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

FILE = Path(__file__).resolve().parent.parent / "config" / "coins.json"
TZ = ZoneInfo("Asia/Tehran")


def _today():
    return datetime.now(TZ).date().isoformat()


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except Exception:
        return {}


def _save(data):
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _user(data, chat_id, user_id, name):
    group = data.setdefault("users", {}).setdefault(str(chat_id), {})
    user = group.setdefault(str(user_id), {"name": name or "Unknown User", "coins": 0, "wins": 0})
    if name:
        user["name"] = name
    return user


def award(chat_id, user_id, name, coins, win=True):
    data = _load()
    user = _user(data, chat_id, user_id, name)
    user["coins"] += int(coins)
    if win:
        user["wins"] += 1
    _save(data)
    return user["coins"]


def record_message(chat_id, user_id, name):
    data = _load()
    today = _today()
    day = data.setdefault("daily_messages", {}).setdefault(today, {}).setdefault(str(chat_id), {})
    entry = day.setdefault(str(user_id), {"name": name or "Unknown User", "messages": 0})
    if name:
        entry["name"] = name
    entry["messages"] += 1
    _save(data)


def settle_previous_days():
    """Award daily top three once; returns awarded records for optional logging."""
    data = _load()
    today = _today()
    paid = data.setdefault("paid_days", [])
    awards = []
    for day, groups in data.setdefault("daily_messages", {}).items():
        if day >= today or day in paid:
            continue
        for chat_id, users in groups.items():
            ranking = sorted(users.items(), key=lambda item: item[1]["messages"], reverse=True)[:3]
            for index, (user_id, entry) in enumerate(ranking):
                amount = (12, 8, 5)[index]
                user = _user(data, chat_id, user_id, entry.get("name"))
                user["coins"] += amount
                awards.append((chat_id, user_id, amount))
        paid.append(day)
    _save(data)
    return awards
