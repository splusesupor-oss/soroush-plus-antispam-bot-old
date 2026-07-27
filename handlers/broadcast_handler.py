"""Private SPlusthon broadcast workflow for the global owner.

Formatting contract
-------------------
A Soroush Plus announcement carries its styling in ``message.entities``
(MessageEntityBold, MessageEntityBlockquote, ...), never in the raw text. The
workflow therefore:

* reads the entities off the incoming event instead of only ``text``,
* stores them next to the text while awaiting confirmation,
* re-sends them with ``formatting_entities=`` to every group.

Two details are easy to get wrong and are handled explicitly here:

* Entity offsets are UTF-16 code-unit positions relative to the *start of the
  message*. Wrapping the announcement in a preview header shifts every offset,
  so preview entities are rebuilt with the header length added.
* ``event.reply``/``send_message`` drop all styling when given plain ``text``
  only; the entity list must be passed through on every send.
"""
import asyncio

from modules.broadcast_state import begin, clear, consume_confirmation, get, set_message
from modules.group_storage import is_active, load_groups


PROMPT = "📢 متن اطلاع‌رسانی را ارسال کنید."

PREVIEW_HEADER = (
    "━━━━━━━━━━━━━━\n\n"
    "📢 پیش‌نمایش اطلاع‌رسانی\n\n"
)
PREVIEW_FOOTER = (
    "\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "ارسال شود؟\n\n"
    "✅ تایید\n"
    "❌ لغو"
)


def _u16_len(value):
    """Length in UTF-16 code units, the unit MessageEntity offsets use."""
    return len((value or "").encode("utf-16-le")) // 2


def _log_phase(bot, phase, owner_id="", reason=""):
    bot.logger.log_info(f"{phase} owner_id={owner_id} {reason}".strip())


def _describe_entities(entities):
    """Readable summary such as 'Bold@0+12, Blockquote@20+40'."""
    if not entities:
        return "<none>"
    parts = []
    for entity in entities:
        name = type(entity).__name__.replace("MessageEntity", "")
        parts.append(
            f"{name}@{getattr(entity, 'offset', '?')}+{getattr(entity, 'length', '?')}"
        )
    return ", ".join(parts)


def _extract_message_entities(event):
    """Pull the formatting entities off an incoming event, if any."""
    message = getattr(event, "message", None)
    entities = getattr(message, "entities", None)
    return list(entities) if entities else []


def _clone_entity_shifted(entity, shift):
    """Copy an entity with its offset moved by ``shift`` UTF-16 units.

    Every attribute is preserved, so entity kinds carrying extra data (custom
    emoji document_id, text URLs, pre language, mention user) survive intact.
    """
    clone = entity.__class__.__new__(entity.__class__)
    source = getattr(entity, "__dict__", None)
    if source is None:
        return entity
    clone.__dict__.update(source)
    clone.offset = getattr(entity, "offset", 0) + shift
    return clone


def _shift_entities(entities, shift):
    if not entities:
        return []
    return [_clone_entity_shifted(entity, shift) for entity in entities]


async def _broadcast_reply(bot, event, text, entities=None):
    message = await event.reply(text, formatting_entities=entities or None)
    if message is not None:
        message_id = getattr(message, "id", None)
        if message_id is not None:
            if not hasattr(bot, "broadcast_bot_message_ids"):
                bot.broadcast_bot_message_ids = set()
            bot.broadcast_bot_message_ids.add(message_id)
    return message


def _preview(text, entities=None):
    """Build the preview body and re-align entity offsets to it."""
    preview_text = f"{PREVIEW_HEADER}{text}{PREVIEW_FOOTER}"
    preview_entities = _shift_entities(entities, _u16_len(PREVIEW_HEADER))
    return preview_text, preview_entities


async def _broadcast_to_groups(bot, text, entities=None):
    successful = 0
    failed = 0
    seen_group_ids = set()
    entities = list(entities) if entities else []

    _log_phase(
        bot,
        "BROADCAST SEND START",
        "",
        f"text_len={len(text)} u16_len={_u16_len(text)} "
        f"entity_count={len(entities)} entities=[{_describe_entities(entities)}]",
    )
    try:
        configured = list(load_groups())
    except Exception as error:
        configured = []
        bot.logger.log_error(f"BROADCAST SEND START load_groups FAILED: {error}")
    active_configured = [g for g in configured if is_active(g)]
    _log_phase(
        bot,
        "BROADCAST SEND TARGETS",
        "",
        f"configured_groups={len(configured)} active_configured={len(active_configured)} "
        f"active_ids={active_configured[:10]}",
    )
    if not active_configured:
        bot.logger.log_error(
            "BROADCAST SEND START no active configured groups; "
            "delivery depends entirely on dialog enumeration"
        )

    async def deliver(target, group_id, route):
        nonlocal successful, failed
        try:
            await bot.client.send_message(
                target,
                text,
                formatting_entities=entities or None,
            )
            successful += 1
            _log_phase(
                bot,
                "BROADCAST GROUP SENT",
                "",
                f"group_id={group_id} route={route} entity_count={len(entities)}",
            )
        except Exception as error:
            failed += 1
            bot.logger.log_error(
                f"BROADCAST GROUP FAILED group_id={group_id} route={route}: {error}"
            )

    try:
        async for dialog in bot.client.iter_dialogs():
            if not getattr(dialog, "is_group", False):
                continue
            group_id = getattr(dialog, "id", None)
            group_key = str(group_id)
            if group_id is None or group_key in seen_group_ids or not is_active(group_id):
                continue
            seen_group_ids.add(group_key)
            await deliver(getattr(dialog, "entity", group_id), group_id, "dialog")
            await asyncio.sleep(0.4)
    except Exception as error:
        # Enumeration is optional: configured active groups are still attempted below.
        bot.logger.log_error(f"BROADCAST DIALOG ENUMERATION FAILED: {error}")

    # Always include configured active groups. This covers clients that omit a
    # dialog, return no is_group flag, or cannot enumerate dialogs at all.
    for group_id in load_groups():
        group_key = str(group_id)
        if group_key in seen_group_ids or not is_active(group_id):
            continue
        seen_group_ids.add(group_key)
        await deliver(int(group_id), group_id, "configured_fallback")
        await asyncio.sleep(0.4)

    _log_phase(
        bot,
        "BROADCAST SEND RESULT",
        "",
        f"successful={successful} failed={failed} attempted={len(seen_group_ids)}",
    )
    _log_phase(
        bot,
        "BROADCAST GROUP SUMMARY",
        "",
        f"successful={successful} failed={failed}",
    )
    return successful, failed


async def handle_private_broadcast(bot, event, owner_id, text):
    """Returns True only when the private message belongs to this workflow."""
    raw_text = getattr(getattr(event, "message", None), "message", None) or text or ""
    text = (text or "").strip()
    entities = _extract_message_entities(event)
    state = get(owner_id)

    _log_phase(
        bot,
        "BROADCAST ROUTE ENTER HANDLER",
        owner_id,
        f"text={text[:60]!r} phase={(state or {}).get('phase', '<none>')!r} "
        f"entity_count={len(entities)} entities=[{_describe_entities(entities)}]",
    )

    if text == "اطلاع رسانی":
        begin(owner_id)
        _log_phase(bot, "BROADCAST START", owner_id)
        _log_phase(
            bot,
            "BROADCAST STATE CREATE",
            owner_id,
            f"phase={(get(owner_id) or {}).get('phase')!r}",
        )
        _log_phase(bot, "WAITING_FOR_TEXT", owner_id)
        try:
            await _broadcast_reply(bot, event, PROMPT)
        except Exception as error:
            bot.logger.log_error(
                f"BROADCAST STATE CREATE reply FAILED owner_id={owner_id} "
                f"error={error!r}"
            )
            raise
        _log_phase(bot, "BROADCAST PROMPT SENT", owner_id)
        return True

    if not state:
        _log_phase(
            bot,
            "BROADCAST ROUTE SKIP",
            owner_id,
            "reason=no_active_session (text is not اطلاع رسانی)",
        )
        return False

    if state["phase"] == "awaiting_confirmation":
        if text in {"لغو", "❌ لغو"}:
            clear(owner_id)
            _log_phase(bot, "STATE CLEARED", owner_id, "reason=cancel")
            await _broadcast_reply(bot, event, "❌ اطلاع‌رسانی لغو شد.")
            return True

        if text in {"تایید", "✅ تایید"}:
            _log_phase(bot, "CONFIRMED", owner_id)
            _log_phase(bot, "BROADCAST CONFIRM", owner_id, "action=consume_state")
            announcement_text, announcement_entities = consume_confirmation(owner_id)
            if announcement_text is None:
                _log_phase(bot, "STATE CLEARED", owner_id, "reason=no_active_session")
                return False
            _log_phase(bot, "STATE CLEARED", owner_id, "reason=confirmed")
            _log_phase(
                bot,
                "BROADCAST STARTED",
                owner_id,
                f"entity_count={len(announcement_entities)} "
                f"entities=[{_describe_entities(announcement_entities)}]",
            )
            try:
                successful, failed = await _broadcast_to_groups(
                    bot, announcement_text, announcement_entities
                )
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
        _log_phase(
            bot,
            "BROADCAST MESSAGE RECEIVED",
            owner_id,
            f"text_len={len(raw_text)} u16_len={_u16_len(raw_text)} "
            f"entity_count={len(entities)} entities=[{_describe_entities(entities)}]",
        )
        if text in {"تایید", "✅ تایید", "لغو", "❌ لغو"}:
            await _broadcast_reply(bot, event, "📢 ابتدا متن اطلاع‌رسانی را ارسال کنید.")
            return True

        # The unstripped body is stored: stripping would shift every entity
        # offset and misalign the formatting.
        set_message(owner_id, raw_text, entities)
        _log_phase(
            bot,
            "BROADCAST MESSAGE STORED",
            owner_id,
            f"text_len={len(raw_text)} u16_len={_u16_len(raw_text)} "
            f"entity_count={len(entities)} entities=[{_describe_entities(entities)}]",
        )
        preview_text, preview_entities = _preview(raw_text, entities)
        _log_phase(
            bot,
            "PREVIEW CREATED",
            owner_id,
            f"shift={_u16_len(PREVIEW_HEADER)} "
            f"preview_entities=[{_describe_entities(preview_entities)}]",
        )
        await _broadcast_reply(bot, event, preview_text, preview_entities)
        return True

    # The sending state is intentionally not allowed to recreate a preview.
    return True
