"""Private SPlusthon broadcast workflow for the global owner."""
import asyncio

from modules.broadcast_state import begin, clear, consume_confirmation, get, set_message
from modules.group_id import normalize_group_id
from modules.group_storage import is_active, load_groups


PROMPT = "📢 متن اطلاع‌رسانی را ارسال کنید."


def _log_phase(bot, phase, owner_id, reason=""):
    bot.logger.log_info(f"{phase} owner_id={owner_id} {reason}".strip())


async def _broadcast_reply(bot, event, text):
    message = await event.reply(text)
    if message is not None:
        message_id = getattr(message, "id", None)
        if message_id is not None:
            if not hasattr(bot, "broadcast_bot_message_ids"):
                bot.broadcast_bot_message_ids = set()
            bot.broadcast_bot_message_ids.add(message_id)
    return message


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
    """پیام را فقط با entity معتبر SPlusthon به گروه‌های فعال می‌فرستد."""
    active_groups = {
        normalize_group_id(group_id)
        for group_id in load_groups()
        if is_active(group_id)
    }
    successful = 0
    failed = 0
    delivered = set()
    bot.logger.log_info(f"BROADCAST LOADED {len(active_groups)} ACTIVE GROUPS")

    try:
        async for dialog in bot.client.iter_dialogs():
            entity = getattr(dialog, "entity", None)
            group_id = normalize_group_id(getattr(dialog, "id", None))
            entity_type = entity.__class__.__name__ if entity else ""
            if group_id not in active_groups or entity_type not in {"Channel", "Chat"}:
                continue
            if group_id in delivered:
                continue
            delivered.add(group_id)
            bot.logger.log_info(f"BROADCAST SENDING TO GROUP: {group_id}")
            try:
                await bot.client.send_message(entity, text)
                successful += 1
                bot.logger.log_info(f"BROADCAST SEND SUCCESS: {group_id}")
            except Exception as error:
                failed += 1
                bot.logger.log_error(f"BROADCAST SEND FAILED: {group_id}: {error!r}")
            await asyncio.sleep(0.4)
    except Exception as error:
        bot.logger.log_error(f"BROADCAST DIALOG LOAD FAILED: {error!r}")

    # گروه‌های فعالِ بدون dialog/entity همچنان جداگانه تلاش می‌شوند.
    for group_id in active_groups - delivered:
        bot.logger.log_info(f"BROADCAST SENDING TO GROUP: {group_id} fallback")
        try:
            entity = await bot.client.get_input_entity(int(group_id))
            await bot.client.send_message(entity, text)
            successful += 1
            bot.logger.log_info(f"BROADCAST SEND SUCCESS: {group_id}")
        except Exception as error:
            failed += 1
            bot.logger.log_error(f"BROADCAST SEND FAILED: {group_id}: {error!r}")
        await asyncio.sleep(0.4)

    return successful, failed


async def handle_private_broadcast(bot, event, owner_id, text):
    """Returns True only when the private message belongs to this workflow."""
    text = text.strip()
    state = get(owner_id)

    if text == "اطلاع رسانی":
        begin(owner_id)
        _log_phase(bot, "BROADCAST OWNER VERIFIED", owner_id)
        _log_phase(bot, "BROADCAST START", owner_id)
        _log_phase(bot, "WAITING_FOR_TEXT", owner_id)
        await _broadcast_reply(bot, event, PROMPT)
        return True

    if not state:
        return False

    if state["phase"] == "awaiting_confirmation":
        if text in {"لغو", "❌ لغو"}:
            clear(owner_id)
            _log_phase(bot, "STATE CLEARED", owner_id, "reason=cancel")
            await _broadcast_reply(bot, event, "❌ اطلاع‌رسانی لغو شد.")
            return True

        if text in {"تایید", "✅ تایید"}:
            _log_phase(bot, "CONFIRMED", owner_id)
            announcement_text = consume_confirmation(owner_id)
            if announcement_text is None:
                _log_phase(bot, "STATE CLEARED", owner_id, "reason=no_active_session")
                return False
            _log_phase(bot, "STATE CLEARED", owner_id, "reason=confirmed")
            _log_phase(bot, "BROADCAST STARTED", owner_id)
            try:
                successful, failed = await _broadcast_to_groups(bot, announcement_text)
                await _broadcast_reply(
                    bot,
                    event,
                    "✅ اطلاع‌رسانی پایان یافت.\n\n"
                    f"گروه‌های موفق: {successful}\n"
                    f"گروه‌های ناموفق: {failed}"
                )
                _log_phase(bot, "BROADCAST FINISHED", owner_id)
            finally:
                clear(owner_id)
            return True

        await _broadcast_reply(bot, event, "برای ارسال «✅ تایید» یا برای لغو «❌ لغو» را ارسال کنید.")
        return True

    if state["phase"] == "awaiting_message":
        if text in {"تایید", "✅ تایید", "لغو", "❌ لغو"}:
            await _broadcast_reply(bot, event, "📢 ابتدا متن اطلاع‌رسانی را ارسال کنید.")
            return True
        set_message(owner_id, text)
        _log_phase(bot, "BROADCAST MESSAGE CAPTURED", owner_id)
        _log_phase(bot, "PREVIEW CREATED", owner_id)
        await _broadcast_reply(bot, event, _preview(text))
        return True

    # The sending state is intentionally not allowed to recreate a preview.
    return True
