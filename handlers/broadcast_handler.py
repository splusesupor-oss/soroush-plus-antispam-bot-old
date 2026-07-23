"""Private SPlusthon broadcast workflow for the global owner."""
from modules.broadcast_state import begin, clear, get, set_message, set_sending
from modules.group_storage import load_groups


PROMPT = "📢 متن اطلاع‌رسانی را ارسال کنید."


def _preview(text):
    return (
        "━━━━━━━━━━━━━━\n\n"
        "📢 پیش‌نمایش اطلاع‌رسانی\n\n"
        f"{text}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "ارسال شود؟\n\n"
        "✅ تایید\n"
        "❌ لغو"
    )


async def _broadcast_to_groups(bot, text):
    successful = 0
    failed = 0
    seen_group_ids = set()

    try:
        async for dialog in bot.client.iter_dialogs():
            if not getattr(dialog, "is_group", False):
                continue
            group_id = getattr(dialog, "id", None)
            if group_id in seen_group_ids:
                continue
            seen_group_ids.add(group_id)
            try:
                await bot.client.send_message(getattr(dialog, "entity", group_id), text)
                successful += 1
            except Exception:
                failed += 1
        return successful, failed
    except Exception as error:
        bot.logger.log_error(f"خطا در دریافت گروه‌های اطلاع‌رسانی: {error}")

    # Fallback for SPlusthon clients that cannot enumerate dialogs.
    for group_id in load_groups():
        if group_id in seen_group_ids:
            continue
        try:
            await bot.client.send_message(int(group_id), text)
            successful += 1
        except Exception:
            failed += 1
    return successful, failed


async def handle_private_broadcast(bot, event, owner_id, text):
    """Returns True only when the private message belongs to this workflow."""
    text = text.strip()
    state = get(owner_id)

    if text == "اطلاع رسانی":
        begin(owner_id)
        await event.reply(PROMPT)
        return True

    if not state:
        return False

    if state["phase"] == "awaiting_confirmation":
        if text in {"لغو", "❌ لغو"}:
            clear(owner_id)
            await event.reply("❌ اطلاع‌رسانی لغو شد.")
            return True

        if text in {"تایید", "✅ تایید"}:
            announcement_text = set_sending(owner_id)
            if announcement_text is None:
                return True
            try:
                successful, failed = await _broadcast_to_groups(bot, announcement_text)
                await event.reply(
                    "✅ اطلاع‌رسانی پایان یافت.\n\n"
                    f"گروه‌های موفق: {successful}\n"
                    f"گروه‌های ناموفق: {failed}"
                )
            finally:
                clear(owner_id)
            return True

        await event.reply("برای ارسال «✅ تایید» یا برای لغو «❌ لغو» را ارسال کنید.")
        return True

    if state["phase"] == "awaiting_message":
        if text in {"تایید", "✅ تایید", "لغو", "❌ لغو"}:
            await event.reply("📢 ابتدا متن اطلاع‌رسانی را ارسال کنید.")
            return True
        set_message(owner_id, text)
        await event.reply(_preview(text))
        return True

    # The sending state is intentionally not allowed to recreate a preview.
    return True
