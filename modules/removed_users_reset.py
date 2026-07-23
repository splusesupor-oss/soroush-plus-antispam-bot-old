"""رفع اخراج‌های دائمیِ ثبت‌شده توسط سیستم ربات، بدون دست‌زدن به اخراج دستی."""


def _entry_source(entry):
    """منبع رکوردهای قدیمی و جدید را به‌صورت سازگار تشخیص می‌دهد."""
    if not isinstance(entry, dict):
        return "system"
    if entry.get("source"):
        return entry["source"]
    # رکوردهای قدیمیِ اخراج دستی پیش از افزوده‌شدن فیلد source نیز نباید
    # در فرمان ریست اخراجی‌ها وارد شوند.
    if entry.get("reason") == "اخراج دستی توسط مالک یا ادمین":
        return "manual"
    return "system"


def _entry_user_id(entry):
    return entry.get("user_id") if isinstance(entry, dict) else entry


def _is_kicked(permissions):
    """فقط بن کامل (عدم مشاهدهٔ پیام‌ها) را اخراج واقعی در نظر می‌گیرد."""
    participant = getattr(permissions, "participant", None)
    rights = getattr(participant, "banned_rights", None)
    return bool(
        getattr(permissions, "is_banned", False)
        and getattr(rights, "view_messages", False)
    )


async def reset_system_removed_users(client, chat_id, entries, logger):
    """اخراج‌های واقعیِ سیستم را رفع می‌کند و رکوردهای موفق/کهنه را برمی‌گرداند.

    `get_permissions` در SPlusthon از `channels.GetParticipantRequest` استفاده
    می‌کند؛ بنابراین پیش از رفع محدودیت، وضعیت واقعی همان کاربر در همان گروه
    خوانده می‌شود. فقط رکوردهای source=system (و رکوردهای قدیمیِ غیر دستی)
    پردازش می‌شوند.
    """
    released_ids = set()
    removable_entries = []

    for entry in list(entries):
        if _entry_source(entry) != "system":
            continue

        target_id = _entry_user_id(entry)
        if target_id is None:
            continue

        try:
            target = await client.get_entity(target_id)
            permissions = await client.get_permissions(chat_id, target)
        except Exception as error:
            logger.log_error(
                f"خطا در بررسی اخراجی ثبت‌شده {target_id}: {error}"
            )
            continue

        # اگر پیش‌تر دستی آزاد شده است، فقط رکورد کهنهٔ سیستم پاک می‌شود؛
        # این مورد در شمارِ اخراجی‌های واقعاً آزادشده نمی‌آید.
        if not _is_kicked(permissions):
            removable_entries.append(entry)
            continue

        try:
            # در SPlusthon مقدارهای پیش‌فرض True یعنی حذف همهٔ محدودیت‌ها.
            await client.edit_permissions(chat_id, target, until_date=None)
        except Exception as error:
            logger.log_error(f"خطا در رفع اخراجی واقعی {target_id}: {error}")
            continue

        removable_entries.append(entry)
        released_ids.add(str(getattr(target, "id", target_id)))

    remaining_entries = [entry for entry in entries if entry not in removable_entries]
    return len(released_ids), remaining_entries
