"""رفع خطای ``FILE_REQUEST_RECEIVED_ON_CONNECTION_SERVER`` در SPlusthon.

ریشهٔ مشکل
----------
طبق مستندات رسمی MTProto، درخواست‌های فایل مثل ``upload.saveFilePart`` /
``upload.saveBigFilePart`` باید از طریق یک «اتصال/جلسهٔ اختصاصیِ فایل» به
«DC رسانه‌ای» (media DC) ارسال شوند، نه از طریق اتصالِ اصلیِ
«connection server». اگر این درخواست‌ها به یک connection server برسد،
سرور آن را با خطای ``FILE_REQUEST_RECEIVED_ON_CONNECTION_SERVER`` رد
می‌کند.

SPlusthon آپلود را با ``self(request)`` یعنی از طریق همان ``self._sender``
اصلی (که به im-server.splus.ir یعنی connection server وصل است) می‌فرستد؛
بنابراین ``SaveFilePartRequest`` به سرورِ اتصال می‌رسد و رد می‌شود.

راه‌حل
------
این ماژول با monkey-patch کردن ``SoroushClient.__call__``، درخواست‌های
``SaveFilePartRequest`` / ``SaveBigFilePartRequest`` را از طریق یک
``MTProtoSender`` اختصاصی (متصل به media DC خوانده‌شده از config زندهٔ
سرور، یا در نبودِ media DC، یک اتصالِ جداگانه به DC فعلی) ارسال می‌کند.
اگر ساختِ sender رسانه‌ای ممکن نبود، به رفتارِ قبلی (sender اصلی) برمی‌گردد
تا هیچ چیزی بدتر نشود.
"""
import logging

from splusthon import SoroushClient
from splusthon.network import MTProtoSender
from splusthon.tl import functions
from splusthon.tl.alltlobjects import LAYER

_log = logging.getLogger("splusthon_upload_fix")

_FILE_UPLOAD_TYPES = (
    functions.upload.SaveFilePartRequest,
    functions.upload.SaveBigFilePartRequest,
)

_INSTALLED = False
_ORIGINAL_CALL = None


def _find_media_dc(client):
    """media DC را از config زندهٔ سرور پیدا می‌کند.

    طبق پروتکل، dc_option که ``media_only=True`` دارد همان سرورِ مخصوصِ
    فایل است. اگر چندتا بود، سرورِ مربوط به DC فعلی ترجیح داده می‌شود.
    """
    cfg = getattr(client, "_config", None)
    opts = getattr(cfg, "dc_options", None)
    if not opts:
        return None
    current_dc = getattr(getattr(client, "session", None), "dc_id", None)
    media = [d for d in opts if bool(getattr(d, "media_only", False))]
    if not media:
        return None
    for d in media:
        if getattr(d, "id", None) == current_dc:
            return d
    return media[0]


def _fallback_dc(client):
    """بدون media DC در config → از DC فعلی، مشخصاتِ اتصالِ جداگانه را می‌سازد."""
    session = getattr(client, "session", None)
    from types import SimpleNamespace
    return SimpleNamespace(
        id=getattr(session, "dc_id", 3),
        ip_address=getattr(session, "server_address", "im-server.splus.ir"),
        port=getattr(session, "port", 443),
    )


async def _ensure_config(client):
    if getattr(client, "_config", None) is None:
        try:
            client._config = await client(functions.help.GetConfigRequest())
        except Exception as e:  # pragma: no cover - فقط دفاعی
            _log.warning("GetConfig failed while preparing upload: %s", e)


async def _create_media_sender(client, dc):
    """یک MTProtoSender اختصاصی به سرورِ فایل/DC داده‌شده می‌سازد.

    هم‌انند ``_create_exported_sender`` کتابخانه، اما به‌جای
    ``_get_dc`` (که همه‌چیز را به im-server می‌برد) به آدرسِ واقعیِ
    media DC وصل می‌شود.
    """
    sender = MTProtoSender(None, loggers=getattr(client, "_log", None))
    await sender.connect(client._connection(
        dc.ip_address,
        dc.port,
        dc.id,
        loggers=getattr(client, "_log", None),
        proxy=getattr(client, "_proxy", None),
        local_addr=getattr(client, "_local_addr", None),
    ))
    _log.info("Exporting auth for media/file sender DC %s", dc.id)
    auth = await client(functions.auth.ExportAuthorizationRequest(dc.id))
    client._init_request.query = functions.auth.ImportAuthorizationRequest(
        id=auth.id, bytes=auth.bytes)
    req = functions.InvokeWithLayerRequest(LAYER, client._init_request)
    await sender.send(req)
    sender.dc_id = dc.id
    return sender


def _sender_alive(sender):
    try:
        fut = getattr(sender, "disconnected", None)
        return fut is not None and not fut.done()
    except Exception:
        return True


async def _get_media_sender(client):
    """sender مخصوصِ آپلود را برای این کلاینت می‌سازد/برمی‌گرداند (یا None)."""
    sender = getattr(client, "_media_sender", None)
    if sender is not None and _sender_alive(sender):
        return sender
    await _ensure_config(client)
    dc = _find_media_dc(client) or _fallback_dc(client)
    try:
        sender = await _create_media_sender(client, dc)
    except Exception as e:
        _log.warning("Could not create media sender (%s); uploads use main sender", e)
        return None
    client._media_sender = sender
    return sender


def _is_file_upload(request):
    """آیا درخواست (یا لیستی از درخواست‌ها) آپلودِ فایل است؟"""
    reqs = request if isinstance(request, (list, tuple)) else [request]
    return any(isinstance(r, _FILE_UPLOAD_TYPES) for r in reqs)


async def _redirected_call(self, request, ordered=False, flood_sleep_threshold=None,
                           _orig_call=None, _get_sender=None):
    """پیاده‌سازیِ واقعیِ هدایتِ آپلود به media DC (برای تست قابلِ فراخوانی)."""
    get_sender = _get_sender or _get_media_sender
    if _is_file_upload(request):
        media = await get_sender(self)
        if media is not None:
            return await self._call(
                media, request, ordered=ordered,
                flood_sleep_threshold=flood_sleep_threshold)
    orig = _orig_call or _ORIGINAL_CALL
    return await orig(self, request, ordered=ordered,
                      flood_sleep_threshold=flood_sleep_threshold)


def install_media_upload():
    """مونکی‌پچِ ``SoroushClient.__call__`` برای مسیریابیِ آپلود به media DC.

    بی‌ضرر است: فقط درخواست‌های SaveFilePart/SaveBigFilePart را در صورتِ
    در دسترس‌بودنِ sender رسانه‌ای هدایت می‌کند؛ بقیهٔ درخواست‌ها دست‌نخورده
    می‌مانند. چند بار صدا زدنِ آن بی‌اثر است (idempotent).
    """
    global _INSTALLED, _ORIGINAL_CALL
    if _INSTALLED:
        return
    _ORIGINAL_CALL = SoroushClient.__call__

    async def _bound_redirect(self, request, ordered=False, flood_sleep_threshold=None):
        return await _redirected_call(
            self, request, ordered=ordered,
            flood_sleep_threshold=flood_sleep_threshold)

    SoroushClient.__call__ = _bound_redirect
    _INSTALLED = True
