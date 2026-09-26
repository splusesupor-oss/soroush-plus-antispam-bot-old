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


def _log_info(logger, message):
    if logger is None:
        return
    try:
        logger.log_info(message)
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


def _sources(logger):
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
    return groups, expiry_records


def _moment(now):
    value = now or datetime.now(timezone.utc)
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None
            else value.astimezone(timezone.utc))


def build_report(logger=None, now=None):
    """Build the detailed legacy expiry report (used by the existing private route)."""
    moment = _moment(now)
    groups, expiry_records = _sources(logger)
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
                lines.append("⏳ وضعیت: منقضی شده" if remaining is None
                             else f"⏳ باقی‌مانده: {remaining}")
        rows.append("\n".join(lines))

    registered_keys = {str(key) for key in groups}
    for expiry_key in expiry_records:
        if str(expiry_key) not in registered_keys:
            _log_error(logger, "EXPIRY REPORT ORPHAN RECORD "
                       f"group_id={expiry_key!r} reason=not_in_groups_storage")
    return "\n\n".join(rows)


def build_group_list(logger=None, now=None):
    """Build the compact owner-in-group list: group name and remaining time only."""
    moment = _moment(now)
    groups, _expiry_records = _sources(logger)
    if not groups:
        return _HEADER + "\n\nℹ️ هیچ گروه ثبت‌شده‌ای وجود ندارد."

    rows = [_HEADER]
    listed = 0
    for group_id, group in groups.items():
        record = group_expiry.get_record(group_id)
        if not record:
            continue
        expires = group_expiry.expires_at(group_id)
        if expires is None:
            _log_error(logger, "EXPIRY LIST INVALID RECORD "
                       f"group_id={group_id!r} record={record!r}")
            continue
        group = group if isinstance(group, dict) else {}
        title = (str(group.get("title") or "").strip()
                 or str(record.get("title") or "").strip()
                 or "گروه بدون نام")
        listed += 1
        remaining = _remaining_text(expires, moment)
        status = "منقضی شده" if remaining is None else f"{remaining} باقی مانده"
        rows.append(f"{listed}. {title}\n⏳ {status}")

    if not listed:
        return _HEADER + "\n\nℹ️ هیچ تاریخ انقضایی ثبت نشده است."
    return "\n\n".join(rows)


def _find_group(groups, expiry_key):
    """یافتن رکورد گروه با هر شکل ممکن شناسه (کوتاه، -۱۰۰… یا منفی ساده)."""
    if not isinstance(groups, dict):
        return None
    key = str(expiry_key)
    for candidate in (key, f"-{key}", f"-100{key}"):
        if candidate in groups:
            value = groups[candidate]
            return value if isinstance(value, dict) else None
    return None


def sync_expiry_list(logger=None, now=None):
    """🔄 همگام‌سازی دوره‌ای (حداقل هر ۲۴ ساعت) دادهٔ «لیست انقضا».

    این تابع فقط دادهٔ گزارش را با وضعیت واقعی گروه‌ها هماهنگ می‌کند؛
    منقضی شدن واقعی گروه سر زمان واقعی انقضا توسط ناظر (watcher) انجام
    می‌شود و هرگز منتظر این به‌روزرسانی نمی‌ماند.

    • گروه‌هایی که مهلتشان کاملاً تمام شده (منقضی + پیام غیرفعال‌سازی
      ارسال‌شده + گروه غیرفعال) از ذخیره‌سازی انقضا حذف می‌شوند تا گروه
      منقضی‌شده برای همیشه در لیست انقضا باقی نماند. رکوردی که هنوز اعلام
      نشده باشد حفظ می‌شود تا ناظر بتواند کارش را تمام کند.
    • گروه‌های تمدیدشده دست نمی‌خورند؛ تاریخ جدیدشان همین حالا در لیست
      دیده می‌شود چون گزارش همیشه از تاریخ انقضای واقعی خوانده می‌شود.
    • نام گروه‌ها روی رکورد انقضا با نام فعلی در groups.json به‌روز می‌شود.
    """
    moment = _moment(now)
    groups, expiry_records = _sources(logger)
    removed_expired = 0
    refreshed_titles = 0

    for key, record in expiry_records.items():
        try:
            expires = group_expiry.expires_at(key)
        except Exception as error:
            _log_error(logger, f"EXPIRY SYNC PARSE FAILED group_id={key!r} "
                               f"error={error!r}")
            continue
        group = _find_group(groups, key)
        group_active = bool(group and group.get("active"))
        expired = expires is not None and moment >= expires

        # پاک‌سازی فقط وقتی امن است که چرخهٔ انقضا کامل شده باشد:
        # منقضی + اعلام‌شده + غیرفعال. تمدید دوباره رکورد تازه می‌سازد.
        if expired and record.get("notified") and not group_active:
            try:
                if group_expiry.clear_expiry(key):
                    removed_expired += 1
                    _log_info(logger, f"EXPIRY SYNC REMOVED group_id={key!r} "
                                      f"expires_at={record.get('expires_at')!r}")
            except Exception as error:
                _log_error(logger, f"EXPIRY SYNC REMOVE FAILED group_id={key!r} "
                                   f"error={error!r}")
            continue

        fresh_title = str(group.get("title") or "").strip() if group else ""
        if fresh_title and fresh_title != str(record.get("title") or "").strip():
            try:
                if group_expiry.update_title(key, fresh_title):
                    refreshed_titles += 1
                    _log_info(logger, "EXPIRY SYNC TITLE REFRESHED "
                                      f"group_id={key!r} title={fresh_title!r}")
            except Exception as error:
                _log_error(logger, f"EXPIRY SYNC TITLE FAILED group_id={key!r} "
                                   f"error={error!r}")

    try:
        total_records = len(group_expiry.all_records())
    except Exception:
        total_records = 0
    return {
        "removed_expired": removed_expired,
        "refreshed_titles": refreshed_titles,
        "total_records": total_records,
    }
