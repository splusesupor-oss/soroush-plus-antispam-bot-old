"""Instrumentation سبک RPCهای خروجی Soroush Plus، بدون تغییر ترتیب ارسال.

Splits each traced RPC into:

* ``connection_wait_ms`` — queued until the request is written to the wire
* ``rpc_wait_ms`` — wire write until SPlusthon's ``_call`` returns
* ``post_rpc_ms`` — leftover time in the high-level wrapper after ``_call``
* ``total_rpc_ms`` — full high-level or ``_call`` span
"""
import asyncio
import contextvars
import functools
import os
import sys
import time


_RESPONSE_RPC_MS = contextvars.ContextVar("response_rpc_ms", default=0.0)
_RPC_DEPTH = contextvars.ContextVar("outgoing_rpc_depth", default=0)
_OP_STATE = contextvars.ContextVar("outgoing_op_state", default=None)
_CALL_STATE = contextvars.ContextVar("outgoing_call_state", default=None)
_INFLIGHT_RPCS = {}
_RPC_DEBUG = os.getenv("BOT_RPC_DEBUG", "").strip() == "1"
# 400–800ms is normal successful Soroush server RTT, not a local failure.
_RPC_SLOW_WARNING_MS = float(os.getenv("BOT_RPC_SLOW_WARNING_MS", "1500"))

_TRACED_OPS = {
    "send_message",
    "reply",
    "delete_message",
    "ban",
    "mute",
    "moderation",
}

_REQUEST_OPS = {
    "SendMessageRequest": "send_message",
    "DeleteMessagesRequest": "delete_message",
    "EditBannedRequest": "moderation",
    "EditChatDefaultBannedRightsRequest": "moderation",
}


def begin_response_measurement():
    """برای هر handler یک context مستقلِ زمان پاسخ ایجاد می‌کند."""
    return _RESPONSE_RPC_MS.set(0.0)


def response_rpc_ms():
    return _RESPONSE_RPC_MS.get()


def end_response_measurement(token):
    _RESPONSE_RPC_MS.reset(token)


def mark_rpc_on_wire():
    """Stamp the moment this RPC is actually written to the connection.

    Called from send-path hooks (``connection.send`` / ``writer.drain``)
    and from tests. Does nothing when no ``_call`` is in progress.
    """
    call = _CALL_STATE.get()
    if call is None or call.get("send_started") is not None:
        return False
    call["send_started"] = time.perf_counter()
    return True


def pending_rpc_snapshot(sender=None):
    """In-flight traced RPCs, plus SPlusthon ``_pending_state`` size if present."""
    rows = list(_INFLIGHT_RPCS.values())
    sender_pending = 0
    if sender is not None:
        pending = getattr(sender, "_pending_state", None) or {}
        try:
            sender_pending = len(pending)
        except TypeError:
            sender_pending = 0
    return {
        "count": len(rows),
        "sender_pending": sender_pending,
        "request_ids": [row.get("request_id") for row in rows if row.get("request_id")],
        "operations": [row.get("operation") for row in rows if row.get("operation")],
    }


def _format_request_ids(snapshot):
    ids = snapshot.get("request_ids") or ()
    return ",".join(str(item) for item in ids) if ids else "-"


def _format_operations(snapshot):
    ops = snapshot.get("operations") or ()
    return ",".join(str(item) for item in ops) if ops else "-"


def _register_inflight(request, record):
    if request is None:
        return None
    key = id(request)
    _INFLIGHT_RPCS[key] = record
    return key


def _unregister_inflight(key):
    if key is not None:
        _INFLIGHT_RPCS.pop(key, None)


def _chat_id(owner, args, kwargs):
    chat = kwargs.get("entity") or kwargs.get("chat_id")
    if chat is not None:
        return getattr(chat, "id", chat)
    if args and isinstance(args[0], int):
        return args[0]
    return getattr(owner, "chat_id", None)


def _request_chat_id(request):
    if request is None:
        return None
    for attr in ("peer", "channel", "entity", "chat_id"):
        value = getattr(request, attr, None)
        if value is None:
            continue
        for nested in ("channel_id", "chat_id", "user_id", "id"):
            found = getattr(value, nested, None)
            if found is not None:
                return found
        if isinstance(value, int):
            return value
    return None


def _request_name(request):
    return type(request).__name__ if request is not None else "unknown"


def _operation_from_request(request):
    return _REQUEST_OPS.get(_request_name(request))


def _extract_request(args, kwargs):
    request = kwargs.get("request")
    if request is not None:
        return request
    if len(args) >= 2 and not isinstance(args[1], (int, str, bytes)):
        return args[1]
    if args and not isinstance(args[0], (int, str, bytes)):
        maybe = args[0]
        # First positional of ``_call`` is usually the sender.
        if len(args) >= 2:
            return args[1]
        name = type(maybe).__name__
        if name.endswith("Request") or name in _REQUEST_OPS:
            return maybe
    return None


def _caller_source():
    frame = sys._getframe(2)
    while frame is not None:
        filename = frame.f_code.co_filename.replace("\\", "/")
        if "outgoing_profiler.py" not in filename:
            return frame.f_code.co_name or "unknown"
        frame = frame.f_back
    return "unknown"


def _format_trace(fields):
    parts = ["RPC TRACE"]
    for key in (
        "request_id",
        "operation",
        "chat_id",
        "connection_wait_ms",
        "rpc_wait_ms",
        "post_rpc_ms",
        "total_rpc_ms",
        "result",
        "request",
    ):
        if key not in fields or fields[key] is None:
            continue
        value = fields[key]
        if isinstance(value, float):
            parts.append(f"{key}={value:.2f}")
        else:
            parts.append(f"{key}={value}")
    return " ".join(parts)


def _log_trace(logger, fields):
    line = _format_trace(fields)
    if str(fields.get("result", "")).startswith("failed"):
        logger.log_error(line)
    else:
        logger.log_info(line)


def _hook_method(obj, name):
    original = getattr(obj, name, None)
    if original is None or getattr(original, "_outgoing_send_hook", False):
        return False

    def _stamp():
        if name == "drain" and not getattr(obj, "_pending", None):
            return
        mark_rpc_on_wire()

    if asyncio.iscoroutinefunction(original):
        async def hooked(*args, **kwargs):
            _stamp()
            return await original(*args, **kwargs)
    else:
        def hooked(*args, **kwargs):
            _stamp()
            return original(*args, **kwargs)

    hooked._outgoing_send_hook = True
    try:
        setattr(obj, name, hooked)
        return True
    except (AttributeError, TypeError):
        return False


def _ensure_send_hooks(client):
    """Hook the live sender/connection once it exists (after connect)."""
    if getattr(client, "_outgoing_send_hooks", False):
        return
    sender = getattr(client, "_sender", None)
    if sender is None:
        return
    hooked = False
    conn = getattr(sender, "_connection", None)
    if conn is not None:
        hooked = _hook_method(conn, "send") or hooked
        writer = getattr(conn, "_writer", None)
        if writer is not None:
            hooked = _hook_method(writer, "drain") or hooked
            ws = getattr(writer, "_ws", None)
            if ws is not None:
                hooked = _hook_method(ws, "send_bytes") or hooked
    if hooked:
        try:
            client._outgoing_send_hooks = True
        except (AttributeError, TypeError):
            pass


def _wrap_existing(obj, name, factory):
    original = getattr(obj, name, None)
    if original is None or getattr(original, "_outgoing_reconnect_hook", False):
        return False
    hooked = factory(original)
    hooked._outgoing_reconnect_hook = True
    try:
        setattr(obj, name, hooked)
        return True
    except (AttributeError, TypeError):
        return False


def _ensure_reconnect_hooks(client, logger):
    """Log keepalive/reconnect without changing SPlusthon timing or retries."""
    sender = getattr(client, "_sender", None)
    if sender is None:
        return
    if getattr(sender, "_outgoing_reconnect_hooks", False):
        _hook_websocket_reset(sender, logger)
        return

    def ping_factory(original):
        def hooked(rnd_id):
            outstanding = getattr(sender, "_ping", None)
            snapshot = pending_rpc_snapshot(sender)
            if outstanding is None:
                logger.log_info(
                    "KEEPALIVE PING SENT "
                    f"ping_id={rnd_id} pending_rpc={snapshot['count']} "
                    f"sender_pending={snapshot['sender_pending']}"
                )
            else:
                logger.log_info(
                    "KEEPALIVE PONG TIMEOUT "
                    f"ping_id={outstanding} next_ping_id={rnd_id} "
                    f"pending_rpc={snapshot['count']} "
                    f"sender_pending={snapshot['sender_pending']} "
                    f"request_ids={_format_request_ids(snapshot)} "
                    f"operations={_format_operations(snapshot)}"
                )
            return original(rnd_id)
        return hooked

    def pong_factory(original):
        async def hooked(message):
            pong = getattr(message, "obj", message)
            logger.log_info(
                "KEEPALIVE PONG RECEIVED "
                f"ping_id={getattr(pong, 'ping_id', None)} "
                f"msg_id={getattr(pong, 'msg_id', None)}"
            )
            try:
                return await original(message)
            finally:
                # Original receive handling gets first chance to resolve the
                # pong.  Completed rows are then removed immediately instead
                # of waiting for the periodic stale-state sweep.
                from modules.connection_guard import drop_completed_pending
                drop_completed_pending(sender)
        if not asyncio.iscoroutinefunction(original):
            def sync_hooked(message):
                pong = getattr(message, "obj", message)
                logger.log_info(
                    "KEEPALIVE PONG RECEIVED "
                    f"ping_id={getattr(pong, 'ping_id', None)} "
                    f"msg_id={getattr(pong, 'msg_id', None)}"
                )
                try:
                    return original(message)
                finally:
                    from modules.connection_guard import drop_completed_pending
                    drop_completed_pending(sender)
            return sync_hooked
        return hooked

    def start_factory(original):
        def hooked(error):
            will_start = bool(
                getattr(sender, "_user_connected", False)
                and not getattr(sender, "_reconnecting", False)
            )
            if will_start:
                snapshot = pending_rpc_snapshot(sender)
                logger.log_info(
                    "RECONNECT START "
                    f"reason={error!r} pending_rpc={snapshot['count']} "
                    f"sender_pending={snapshot['sender_pending']} "
                    f"request_ids={_format_request_ids(snapshot)} "
                    f"operations={_format_operations(snapshot)}"
                )
            return original(error)
        return hooked

    def reconnect_factory(original):
        async def hooked(last_error):
            started = time.perf_counter()
            snapshot = pending_rpc_snapshot(sender)
            try:
                result = await original(last_error)
            except Exception as error:
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.log_info(
                    "RECONNECT FAILED "
                    f"error={error!r} elapsed_ms={elapsed_ms:.1f} "
                    f"pending_rpc={snapshot['count']} "
                    f"request_ids={_format_request_ids(snapshot)}"
                )
                raise
            elapsed_ms = (time.perf_counter() - started) * 1000
            connected = bool(getattr(sender, "_user_connected", False))
            label = "RECONNECT SUCCESS" if connected else "RECONNECT FAILED"
            logger.log_info(
                f"{label} elapsed_ms={elapsed_ms:.1f} "
                f"pending_rpc={snapshot['count']} "
                f"sender_pending={pending_rpc_snapshot(sender)['sender_pending']} "
                f"request_ids={_format_request_ids(snapshot)}"
            )
            return result
        if not asyncio.iscoroutinefunction(original):
            def sync_hooked(last_error):
                started = time.perf_counter()
                snapshot = pending_rpc_snapshot(sender)
                try:
                    result = original(last_error)
                except Exception as error:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    logger.log_info(
                        "RECONNECT FAILED "
                        f"error={error!r} elapsed_ms={elapsed_ms:.1f} "
                        f"pending_rpc={snapshot['count']} "
                        f"request_ids={_format_request_ids(snapshot)}"
                    )
                    raise
                elapsed_ms = (time.perf_counter() - started) * 1000
                connected = bool(getattr(sender, "_user_connected", False))
                label = "RECONNECT SUCCESS" if connected else "RECONNECT FAILED"
                logger.log_info(
                    f"{label} elapsed_ms={elapsed_ms:.1f} "
                    f"pending_rpc={snapshot['count']} "
                    f"request_ids={_format_request_ids(snapshot)}"
                )
                return result
            return sync_hooked
        return hooked

    original_pong = getattr(sender, "_handle_pong", None)
    _wrap_existing(sender, "_keepalive_ping", ping_factory)
    _wrap_existing(sender, "_handle_pong", pong_factory)
    hooked_pong = getattr(sender, "_handle_pong", None)
    handlers = getattr(sender, "_handlers", None)
    if (
        isinstance(handlers, dict)
        and original_pong is not None
        and hooked_pong is not None
        and hooked_pong is not original_pong
    ):
        orig_func = getattr(original_pong, "__func__", original_pong)
        for key, value in list(handlers.items()):
            if value is original_pong or getattr(value, "__func__", None) is orig_func:
                handlers[key] = hooked_pong
    _wrap_existing(sender, "_start_reconnect", start_factory)
    _wrap_existing(sender, "_reconnect", reconnect_factory)
    _hook_websocket_reset(sender, logger)
    try:
        sender._outgoing_reconnect_hooks = True
    except (AttributeError, TypeError):
        pass


def _hook_websocket_reset(sender, logger):
    conn = getattr(sender, "_connection", None)
    if conn is None:
        return
    original = getattr(conn, "_connection_guard_reset_once", None)
    if original is None or getattr(original, "_outgoing_reconnect_hook", False):
        return

    async def hooked():
        snapshot = pending_rpc_snapshot(sender)
        logger.log_info(
            "WEBSOCKET RESET START reason=periodic "
            f"pending_rpc={snapshot['count']} "
            f"sender_pending={snapshot['sender_pending']} "
            f"request_ids={_format_request_ids(snapshot)}"
        )
        try:
            result = await original()
        except Exception as error:
            logger.log_info(f"WEBSOCKET RESET FAILED error={error!r}")
            raise
        logger.log_info("WEBSOCKET RESET SUCCESS")
        return result

    if not asyncio.iscoroutinefunction(original):
        return
    hooked._outgoing_reconnect_hook = True
    try:
        conn._connection_guard_reset_once = hooked
    except (AttributeError, TypeError):
        pass


def _wrap_connect(client, logger):
    original = getattr(client, "connect", None)
    if original is None or getattr(original, "_outgoing_reconnect_hook", False):
        return False

    async def hooked(*args, **kwargs):
        result = await original(*args, **kwargs)
        _ensure_send_hooks(client)
        _ensure_reconnect_hooks(client, logger)
        return result

    if not asyncio.iscoroutinefunction(original):
        def sync_hooked(*args, **kwargs):
            result = original(*args, **kwargs)
            _ensure_send_hooks(client)
            _ensure_reconnect_hooks(client, logger)
            return result
        sync_hooked._outgoing_reconnect_hook = True
        try:
            client.connect = sync_hooked
            return True
        except (AttributeError, TypeError):
            return False

    hooked._outgoing_reconnect_hook = True
    try:
        client.connect = hooked
        return True
    except (AttributeError, TypeError):
        return False


def _wrap_call(client, logger):
    original = getattr(client, "_call", None)
    if original is None or getattr(original, "_outgoing_profiled", False):
        return False

    @functools.wraps(original)
    async def measured(*args, **kwargs):
        _ensure_send_hooks(client)
        _ensure_reconnect_hooks(client, logger)
        request = _extract_request(args, kwargs)
        op_state = _OP_STATE.get()
        operation = None if op_state is None else op_state.get("operation")
        if not operation:
            operation = _operation_from_request(request)
        chat_id = None if op_state is None else op_state.get("chat_id")
        if chat_id is None:
            chat_id = _request_chat_id(request)
        request_id = None if op_state is None else op_state.get("request_id")
        if not request_id:
            request_id = f"{id(asyncio.current_task()):x}-{time.monotonic_ns():x}"
        call = {"send_started": None, "queued": time.perf_counter()}
        token = _CALL_STATE.set(call)
        inflight_key = _register_inflight(request, {
            "request_id": request_id,
            "operation": operation or _request_name(request),
            "chat_id": chat_id,
            "request": _request_name(request),
        })
        result = "success"
        try:
            return await original(*args, **kwargs)
        except asyncio.CancelledError:
            result = "cancelled"
            raise
        except Exception as error:
            result = f"failed:{error.__class__.__name__}"
            raise
        finally:
            returned = time.perf_counter()
            send_started = call.get("send_started")
            if send_started is None:
                connection_wait_ms = 0.0
                rpc_wait_ms = (returned - call["queued"]) * 1000
            else:
                connection_wait_ms = (send_started - call["queued"]) * 1000
                rpc_wait_ms = (returned - send_started) * 1000
            post_rpc_ms = (time.perf_counter() - returned) * 1000
            total_rpc_ms = (time.perf_counter() - call["queued"]) * 1000
            _CALL_STATE.reset(token)
            _unregister_inflight(inflight_key)
            record = {
                "request_id": request_id,
                "operation": operation or _request_name(request),
                "chat_id": chat_id,
                "connection_wait_ms": connection_wait_ms,
                "rpc_wait_ms": rpc_wait_ms,
                "post_rpc_ms": post_rpc_ms,
                "total_rpc_ms": total_rpc_ms,
                "result": result,
                "request": _request_name(request),
            }
            if op_state is not None:
                op_state.setdefault("calls", []).append(record)
                op_state["last_return"] = time.perf_counter()
            should_log = (
                (operation in _TRACED_OPS)
                or _RPC_DEBUG
                or _operation_from_request(request) in _TRACED_OPS
            )
            if should_log:
                _log_trace(logger, record)

    measured._outgoing_profiled = True
    try:
        client._call = measured
        return True
    except (AttributeError, TypeError):
        return False


def _wrap(owner, attribute, operation, logger):
    original = getattr(owner, attribute, None)
    if original is None or getattr(original, "_outgoing_profiled", False):
        return False

    @functools.wraps(original)
    async def measured(*args, **kwargs):
        request_id = f"{id(asyncio.current_task()):x}-{time.monotonic_ns():x}"
        chat_id = _chat_id(owner, args, kwargs)
        started_wall = time.time()
        started = time.perf_counter()
        depth = _RPC_DEPTH.get()
        depth_token = _RPC_DEPTH.set(depth + 1)
        state = {
            "request_id": request_id,
            "operation": operation,
            "chat_id": chat_id,
            "calls": [],
            "last_return": None,
        }
        op_token = _OP_STATE.set(state)
        source = _caller_source()
        if _RPC_DEBUG and operation in {"send_message", "reply"}:
            logger.log_info(
                f"SEND START source={source} chat_id={chat_id}"
            )
        if _RPC_DEBUG:
            logger.log_info(
                "OUTGOING RPC START "
                f"request_id={request_id} operation={operation} chat_id={chat_id} "
                f"started_at={started_wall:.3f}"
            )
        result = "success"
        try:
            return await original(*args, **kwargs)
        except asyncio.CancelledError:
            result = "cancelled"
            raise
        except Exception as error:
            result = f"failed:{error.__class__.__name__}"
            raise
        finally:
            ended = time.perf_counter()
            elapsed_ms = (ended - started) * 1000
            calls = state.get("calls") or ()
            connection_wait_ms = sum(item["connection_wait_ms"] for item in calls)
            rpc_wait_ms = sum(item["rpc_wait_ms"] for item in calls)
            last_return = state.get("last_return")
            if last_return is None:
                post_rpc_ms = 0.0 if calls else elapsed_ms
            else:
                post_rpc_ms = max(0.0, (ended - last_return) * 1000)
            if depth == 0:
                _RESPONSE_RPC_MS.set(_RESPONSE_RPC_MS.get() + elapsed_ms)
            _OP_STATE.reset(op_token)
            _RPC_DEPTH.reset(depth_token)
            if operation in _TRACED_OPS:
                _log_trace(logger, {
                    "request_id": request_id,
                    "operation": operation,
                    "chat_id": chat_id,
                    "connection_wait_ms": connection_wait_ms,
                    "rpc_wait_ms": rpc_wait_ms,
                    "post_rpc_ms": post_rpc_ms,
                    "total_rpc_ms": elapsed_ms,
                    "result": result,
                })
            if _RPC_DEBUG:
                logger.log_info(
                    "OUTGOING RPC FINISHED "
                    f"request_id={request_id} operation={operation} chat_id={chat_id} "
                    f"started_at={started_wall:.3f} finished_at={time.time():.3f} "
                    f"rpc_ms={elapsed_ms:.2f} result={result} nested={depth > 0}"
                )
            if _RPC_DEBUG and operation in {"send_message", "reply"}:
                logger.log_info(
                    f"SEND END source={source} ms={elapsed_ms:.0f}"
                )
            if elapsed_ms >= 250:
                logger.log_info(
                    "RPC TIME "
                    f"operation={operation} chat_id={chat_id} "
                    f"rpc_ms={elapsed_ms:.1f} result={result}"
                )
            if elapsed_ms > _RPC_SLOW_WARNING_MS:
                line = (
                    "OUTGOING RPC WARNING "
                    f"request_id={request_id} operation={operation} "
                    f"chat_id={chat_id} rpc_ms={elapsed_ms:.2f} result={result}"
                )
                if result.startswith("failed"):
                    logger.log_error(line)
                else:
                    # A slow success is diagnostic, not an ERROR.  This keeps
                    # genuine failures visually distinct in production logs.
                    logger.log_info(line)

    measured._outgoing_profiled = True
    try:
        setattr(owner, attribute, measured)
        return True
    except (AttributeError, TypeError):
        return False


def instrument_client(client, logger):
    """یک بار پس از ساخت client فراخوانی می‌شود."""
    if getattr(client, "_outgoing_profiler_installed", False):
        return
    _wrap_call(client, logger)
    for attribute, operation in (
        ("send_message", "send_message"),
        ("edit_message", "edit_message"),
        ("delete_messages", "delete_message"),
        ("edit_permissions", "moderation"),
        ("kick_participant", "ban"),
    ):
        _wrap(client, attribute, operation, logger)
    _ensure_send_hooks(client)
    _ensure_reconnect_hooks(client, logger)
    try:
        client._outgoing_profiler_installed = True
    except (AttributeError, TypeError):
        pass


def instrument_event(event, logger):
    """reply/delete رویداد را جدا از RPC داخلی client هم اندازه می‌گیرد."""
    if getattr(event, "_outgoing_profiler_installed", False):
        return
    _wrap(event, "reply", "reply", logger)
    _wrap(event, "delete", "delete_message", logger)
    try:
        event._outgoing_profiler_installed = True
    except (AttributeError, TypeError):
        pass
