"""Instrumentation سبک RPCهای خروجی Soroush Plus، بدون تغییر ترتیب ارسال."""
import asyncio
import contextvars
import functools
import time


_RESPONSE_RPC_MS = contextvars.ContextVar("response_rpc_ms", default=0.0)
_RPC_DEPTH = contextvars.ContextVar("outgoing_rpc_depth", default=0)


def begin_response_measurement():
    """برای هر handler یک context مستقلِ زمان پاسخ ایجاد می‌کند."""
    return _RESPONSE_RPC_MS.set(0.0)


def response_rpc_ms():
    return _RESPONSE_RPC_MS.get()


def end_response_measurement(token):
    _RESPONSE_RPC_MS.reset(token)


def _chat_id(args, kwargs):
    return kwargs.get("entity") or kwargs.get("chat_id") or (args[0] if args else None)


def _wrap(owner, attribute, operation, logger):
    original = getattr(owner, attribute, None)
    if original is None or getattr(original, "_outgoing_profiled", False):
        return False

    @functools.wraps(original)
    async def measured(*args, **kwargs):
        request_id = f"{id(asyncio.current_task()):x}-{time.monotonic_ns():x}"
        chat_id = _chat_id(args, kwargs)
        started_wall = time.time()
        started = time.perf_counter()
        depth = _RPC_DEPTH.get()
        depth_token = _RPC_DEPTH.set(depth + 1)
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
            elapsed_ms = (time.perf_counter() - started) * 1000
            if depth == 0:
                _RESPONSE_RPC_MS.set(_RESPONSE_RPC_MS.get() + elapsed_ms)
            _RPC_DEPTH.reset(depth_token)
            logger.log_info(
                "OUTGOING RPC FINISHED "
                f"request_id={request_id} operation={operation} chat_id={chat_id} "
                f"started_at={started_wall:.3f} finished_at={time.time():.3f} "
                f"rpc_ms={elapsed_ms:.2f} result={result} nested={depth > 0}"
            )
            if elapsed_ms > 50:
                logger.log_error(
                    "OUTGOING RPC WARNING "
                    f"request_id={request_id} operation={operation} "
                    f"chat_id={chat_id} rpc_ms={elapsed_ms:.2f}"
                )

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
    for attribute, operation in (
        ("send_message", "send_message"),
        ("edit_message", "edit_message"),
        ("delete_messages", "delete_message"),
    ):
        _wrap(client, attribute, operation, logger)
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
