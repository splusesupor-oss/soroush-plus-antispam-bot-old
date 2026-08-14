"""📋 گزارش فقط-خواندنی انقضای گروه‌ها.

این ماژول هیچ فایل یا state جدیدی نمی‌سازد. اطلاعات گروه‌ها را از
``modules.group_storage`` و مهلت‌ها را از ``modules.group_expiry`` می‌خواند.
هر دو منبع cache وابسته به mtime دارند، پس هر فراخوان گزارش آخرین تغییر
فایل‌ها را می‌بیند.
"""
from datetime import datetime, timezone

from modules import group_expiry, group_storage

_HEADER = "📋 لیست انقضای گروه‌ها"
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _log_error(logger, message):
    if logger is None:
        return
    try:
        logger.log_error(message)
    except Exception:
        pass


def _digits(value):
    return str(value).translate(_PERSIAN_DIGITS)


def _remaining_text(expires_at, now):
    """Format an aware UTC expiry moment without timezone-dependent rounding."""
    seconds = int((expires_at - now).total_seconds())
    if seconds <= 0:
        return None
    days, remainder = divmod(seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{_digits(days)} روز")
    if hours or days:
        parts.append(f"{_digits(hours)} ساعت")
    if not days and not hours:
        parts.append(f"{_digits(minutes)} دقیقه")
    return " و ".join(parts)


def build_report(logger=None, now=None):
    """Build the owner-facing report from the live storage sources.

    Malformed/missing data is represented in the report or logged; it never
    raises into the private-message event handler.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)

    try:
        groups = group_storage.load_groups()
        groups = groups if isinstance(groups, dict) else {}
    except Exception as error:
        _log_error(logger, f"EXPIRY REPORT GROUP LOAD FAILED error={error!r}")
        groups = {}

    try:
        expiry_records = group_expiry.all_records()
    except Exception as error:
        _log_error(logger, f"EXPIRY REPORT LOAD FAILED error={error!r}")
        expiry_records = {}

    if not groups:
        return _HEADER + "\n\nℹ️ هیچ گروه ثبت‌شده‌ای وجود ندارد."

    rows = [_HEADER]
    for index, (group_id, group) in enumerate(groups.items(), 1):
        group = group if isinstance(group, dict) else {}
        record = group_expiry.get_record(group_id)
        title = (
            str(group.get("title") or "").strip()
            or str((record or {}).get("title") or "").strip()
            or "گروه بدون نام"
        )
        prefix = "❌" if record and group_expiry.is_expired(group_id, now=moment) else f"{_digits(index)}️⃣"
        lines = [f"{prefix} گروه: {title}", f"🆔 شناسه: {group_id}"]

        if not record:
            lines.append("⏳ وضعیت: تاریخ انقضا ثبت نشده")
        else:
            expires = group_expiry.expires_at(group_id)
            if expires is None:
                _log_error(logger, "EXPIRY REPORT INVALID RECORD "
                           f"group_id={group_id!r} record={record!r}")
                lines.append("⏳ وضعیت: تاریخ انقضا نامعتبر است")
            else:
                remaining = _remaining_text(expires, moment)
                if remaining is None:
                    lines.append("⏳ وضعیت: منقضی شده")
                else:
                    lines.append(f"⏳ باقی‌مانده: {remaining}")
        rows.append("\n".join(lines))

    # An expiry entry with no current group registration is intentionally not
    # shown as a usable group, but it is observable in logs for maintenance.
    registered_keys = {str(key) for key in groups}
    for expiry_key in expiry_records:
        if str(expiry_key) not in registered_keys:
            _log_error(logger, "EXPIRY REPORT ORPHAN RECORD "
                       f"group_id={expiry_key!r} reason=not_in_groups_storage")

    return "\n\n".join(rows)
