"""Independent private-chat path: /start + one test inline button.

This module is isolated from group dispatch, Queue, Governor, and RPC
plumbing. Group messages must never enter these helpers.
"""

START_TEXT = (
    "سلام 👋\n"
    "\n"
    "برای تست دکمه اینلاین، گزینه زیر را بزنید."
)
TEST_BUTTON_TEXT = "🧪 دکمه تست"
TEST_BUTTON_DATA = b"test_button"
TEST_BUTTON_DATA_TEXT = "test_button"
TEST_OK_TEXT = "✅ دکمه کار می‌کند"

_GROUP_PEER_MARKERS = ("group", "channel", "chat")
_PRIVATE_PEER_NAMES = {
    "peeruser",
    "inputpeeruser",
    "user",
    "inputuser",
}


def _event_text(event):
    """Read /start text from the fields SPlusthon actually fills."""
    if event is None:
        return ""
    for attr in ("raw_text", "text"):
        value = getattr(event, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    message = getattr(event, "message", None)
    if isinstance(message, str) and message.strip():
        return message
    if message is None:
        return ""
    for attr in ("message", "text", "caption", "raw_text"):
        value = getattr(message, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _type_name(value):
    if value is None:
        return ""
    return type(value).__name__.lower()


def _looks_like_group_peer(name):
    return any(marker in name for marker in _GROUP_PEER_MARKERS)


def _chat_id_int(event):
    chat_id = getattr(event, "chat_id", None) if event is not None else None
    try:
        return int(chat_id)
    except (TypeError, ValueError):
        return None


def is_group_event(event):
    """True only when the event is provably a group/channel, not a DM."""
    if event is None:
        return False
    if bool(getattr(event, "is_group", False) or getattr(event, "is_channel", False)):
        return True
    chat_id_int = _chat_id_int(event)
    if chat_id_int is not None and chat_id_int < 0:
        return True
    peer_name = _type_name(getattr(event, "_chat_peer", None))
    chat_name = _type_name(getattr(event, "chat", None))
    if peer_name in _PRIVATE_PEER_NAMES or chat_name in _PRIVATE_PEER_NAMES:
        return False
    if "channel" in peer_name or "megagroup" in peer_name:
        return True
    if "channel" in chat_name or "megagroup" in chat_name:
        return True
    if peer_name in {"peerchat", "inputpeerchat"} or chat_name in {"peerchat", "inputpeerchat"}:
        return True
    return False


def is_private_event(event):
    """Cheap private-chat check. No RPC and no group-path helpers.

    SPlusthon often leaves ``event.is_private`` False and ``chat_id`` empty
    on a real DM. Negative group/channel ids must never match.
    """
    if event is None:
        return False
    if is_group_event(event):
        return False
    if bool(getattr(event, "is_private", False)):
        return True
    peer_name = _type_name(getattr(event, "_chat_peer", None))
    chat_name = _type_name(getattr(event, "chat", None))
    if peer_name in _PRIVATE_PEER_NAMES or chat_name in _PRIVATE_PEER_NAMES:
        return True
    chat_id_int = _chat_id_int(event)
    if chat_id_int is not None and chat_id_int > 0:
        return True
    return False


def is_start_command(text):
    """True only for /start and /start@botname."""
    cleaned = (
        str(text or "")
        .replace("‌", " ")
        .replace("‏", "")
        .replace("‎", "")
    )
    first = cleaned.strip().split(None, 1)
    if not first:
        return False
    token = first[0].strip()
    if not token:
        return False
    lowered = token.lower()
    if lowered == "/start":
        return True
    return lowered.startswith("/start@")


def start_keyboard():
    """One full-width inline button on its own row."""
    try:
        from splusthon import Button
    except ImportError:
        return None
    try:
        button = Button.inline(TEST_BUTTON_TEXT, data=TEST_BUTTON_DATA)
    except Exception:
        return None
    return [[button]]


def _callback_data_text(event):
    data = getattr(event, "data", None)
    if data is None:
        data = getattr(event, "data_match", None)
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="ignore")
    if data is None:
        return ""
    return str(data)


def is_test_button_callback(event):
    return _callback_data_text(event) == TEST_BUTTON_DATA_TEXT


def _log(bot, message):
    logger = getattr(bot, "logger", None) if bot is not None else None
    if logger is None:
        return
    try:
        logger.log_info(message)
    except Exception:
        pass


def _chat_id(event):
    return getattr(event, "chat_id", None) if event is not None else None


async def _invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


async def _try_send(method, text, kwargs, bot=None):
    if not callable(method):
        return False
    try:
        await _invoke(method, text, **kwargs)
        return True
    except Exception as error:
        _log(bot, f"PV START REPLY FAILED error={error!r} kwargs={bool(kwargs)}")
        if kwargs:
            try:
                await _invoke(method, text)
                return True
            except Exception as retry_error:
                _log(bot, f"PV START REPLY RETRY FAILED error={retry_error!r}")
                return False
        return False


async def send_start_reply(bot, event):
    keyboard = start_keyboard()
    kwargs = {}
    if keyboard is not None:
        kwargs["buttons"] = keyboard
    if await _try_send(getattr(event, "reply", None), START_TEXT, kwargs, bot=bot):
        return True
    client = getattr(bot, "client", None) if bot is not None else None
    chat_id = _chat_id(event)
    send_message = getattr(client, "send_message", None) if client is not None else None
    if callable(send_message) and chat_id is not None:
        try:
            await _invoke(send_message, chat_id, START_TEXT, **kwargs)
            return True
        except Exception as error:
            _log(bot, f"PV START SEND_MESSAGE FAILED error={error!r}")
            try:
                await _invoke(send_message, chat_id, START_TEXT)
                return True
            except Exception as retry_error:
                _log(bot, f"PV START SEND_MESSAGE RETRY FAILED error={retry_error!r}")
                return False
    return False


async def try_handle_private_start(bot, event):
    """Handle PV /start only. Return True when the event was consumed.

    A /start that is not a proven group/channel is treated as PV even when
    SPlusthon leaves is_private=False and chat_id empty. Otherwise it falls
    into the group admin `/` lane and is dropped silently.
    """
    text = _event_text(event)
    start = is_start_command(text)
    group = is_group_event(event)
    private = is_private_event(event)
    if start:
        _log(
            bot,
            "PV START RECEIVED "
            f"chat_id={_chat_id(event)} "
            f"event_is_private={getattr(event, 'is_private', None)} "
            f"private_event={int(private)} "
            f"group_event={int(group)} "
            f"event_out={getattr(event, 'out', None)} "
            f"text={text!r}",
        )
    if not start:
        return False
    if group:
        return False
    _log(bot, f"PV START ROUTED chat_id={_chat_id(event)}")
    _log(bot, f"PV START HANDLER chat_id={_chat_id(event)}")
    sent = await send_start_reply(bot, event)
    if sent:
        _log(bot, f"PV START SENT chat_id={_chat_id(event)}")
        return True
    _log(bot, f"PV START SEND FAILED chat_id={_chat_id(event)}")
    return False


async def handle_private_callback(bot, event):
    """Answer the test button with a visible PV reply."""
    if not is_private_event(event):
        return False
    if not is_test_button_callback(event):
        return False

    _log(bot, f"PV TEST BUTTON RECEIVED chat_id={_chat_id(event)}")

    answer = getattr(event, "answer", None)
    if callable(answer):
        try:
            await answer(TEST_OK_TEXT)
        except Exception as error:
            _log(bot, f"PRIVATE CALLBACK ANSWER FAILED error={error!r}")

    sent = await _try_send(getattr(event, "reply", None), TEST_OK_TEXT, {})
    if not sent:
        edit = getattr(event, "edit", None)
        if callable(edit):
            try:
                await edit(TEST_OK_TEXT)
                sent = True
            except Exception as error:
                _log(bot, f"PRIVATE CALLBACK EDIT FAILED error={error!r}")
    if not sent:
        client = getattr(bot, "client", None) if bot is not None else None
        chat_id = _chat_id(event)
        send_message = getattr(client, "send_message", None) if client is not None else None
        if callable(send_message) and chat_id is not None:
            try:
                await send_message(chat_id, TEST_OK_TEXT)
                sent = True
            except Exception as error:
                _log(bot, f"PRIVATE CALLBACK SEND FAILED error={error!r}")

    if sent:
        _log(bot, f"PV TEST BUTTON RESPONSE SENT chat_id={_chat_id(event)}")
    return sent


def register_private_handlers(bot):
    """Attach the PV callback listener. NewMessage intercept lives in core."""
    client = getattr(bot, "client", None) if bot is not None else None
    if client is None or not hasattr(client, "on"):
        return False
    try:
        from splusthon import events
    except ImportError:
        return False
    callback_query = getattr(events, "CallbackQuery", None)
    if callback_query is None:
        return False

    @client.on(callback_query())
    async def private_test_button(event):
        try:
            await handle_private_callback(bot, event)
        except Exception as error:
            logger = getattr(bot, "logger", None)
            if logger is not None:
                try:
                    logger.log_error(f"PRIVATE CALLBACK FAILED error={error!r}")
                except Exception:
                    pass

    return True
