import json
import os
from datetime import datetime

FILE = "logs/group_stats.json"


def load_stats():
    if not os.path.exists(FILE):
        return {}

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_stats(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_group(data, chat_id):
    chat_id = str(chat_id)

    if chat_id not in data:
        data[chat_id] = {
            "messages": 0,
            "deleted": 0,
            "kicked": 0,
            "muted": 0,
            "users": {}
        }

    return data[chat_id]


def ensure_user(group, user_id, username=""):
    user_id = str(user_id)

    if user_id not in group["users"]:
        group["users"][user_id] = {
            "username": username or "unknown",
            "messages": 0,
            "deleted": 0
        }

    elif username:
        group["users"][user_id]["username"] = username

    return group["users"][user_id]


def add_message(chat_id, user_id, username=""):
    data = load_stats()

    group = ensure_group(data, chat_id)
    user = ensure_user(group, user_id, username)

    group["messages"] += 1
    user["messages"] += 1

    save_stats(data)


def add_deleted(chat_id, user_id, username=""):
    data = load_stats()

    group = ensure_group(data, chat_id)
    user = ensure_user(group, user_id, username)

    group["deleted"] += 1
    user["deleted"] += 1

    save_stats(data)


def add_kick(chat_id):
    data = load_stats()

    group = ensure_group(data, chat_id)
    group["kicked"] += 1

    save_stats(data)


def add_mute(chat_id):
    data = load_stats()

    group = ensure_group(data, chat_id)
    group["muted"] += 1

    save_stats(data)


def get_stats(chat_id):
    data = load_stats()
    return data.get(str(chat_id), {
        "messages": 0,
        "deleted": 0,
        "kicked": 0,
        "muted": 0,
        "members": 0,
        "users": {}
    })


def top_users(chat_id, limit=10):
    group = get_stats(chat_id)

    users = group.get("users", {})

    result = sorted(
        users.items(),
        key=lambda x: x[1].get("messages", 0),
        reverse=True
    )

    return result[:limit]


def make_report(chat_id, member_count=0):
    group = get_stats(chat_id)

    text = (
        "📊 **آمار گروه**\n\n"
        "💬 **کل پیام‌ها:** "
        f"{group['messages']}\n\n"

        "🗑 **پیام حذف شده:** "
        f"{group['deleted']}\n\n"

        "🚪 **اخراج شده:** "
        f"{group['kicked']}\n\n"

        "🔇 **سکوت شده:** "
        f"{group['muted']}\n\n"

        "👥 **تعداد اعضا:** "
        f"{member_count}\n\n"

        "🏆 **کاربران فعال:**\n\n"
    )

    for i, (_, user) in enumerate(top_users(chat_id), 1):
        name = user.get("username", "unknown")
        count = user.get("messages", 0)
        text += f"{i}️⃣ @{name} - {count} پیام\n\n"

    return text

