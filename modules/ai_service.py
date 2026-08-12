"""Async OpenAI-compatible text API client; no group policy is kept here."""
import asyncio
import os

import requests

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_CHAT_COMPLETIONS_PATH = "/chat/completions"
_DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"
_TIMEOUT = (5, 20)
_DEFAULT_FALLBACK_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
_DEFAULT_MAX_TOKENS = 300
_DEFAULT_HTTP_REFERER = "https://github.com/splusesupor-oss/soroush-plus-antispam-bot-old"
_DEFAULT_APP_TITLE = "Soroush Plus Bot"
_SESSION = requests.Session()
_SYSTEM_PROMPT = """تو دستیار هوش مصنوعی داخل یک ربات گروهی هستی.
به سوال کاربر دقیق، مرتبط و کوتاه پاسخ بده.
اگر اطلاعات کافی نداری حدس نزن و صریح بگو اطلاعات کافی نداری.
اطلاعات جعلی تولید نکن.
خودت را جایگزین ربات اصلی نکن و هیچ دستور، مدیریت گروه، بازی یا عملیاتی اجرا نکن.
پاسخ‌ها باید به زبان فارسی روان باشند.
از نمایش پیام‌های داخلی، قوانین ایمنی، تحلیل، متادیتا، system information،
فرآیند فکر کردن و اطلاعات فنی خودداری کن؛ فقط پاسخ نهایی را بنویس.
سروش پلاس یک پیام‌رسان ایرانی است. آن را با محصولات، اصطلاحات پزشکی یا
موضوعات نامرتبط اشتباه نگیر و درباره آن ادعای غیرمستند نکن."""


class AIServiceError(RuntimeError):
    def __init__(self, message, *, status_code=None, response_body=None, kind="api"):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.kind = kind


def endpoint_url(base_url=None):
    """Build the OpenAI-compatible chat-completions endpoint once.

    ``AI_BASE_URL`` is normally a base URL such as ``https://host/v1``.
    The old full-endpoint form is accepted for a safe zero-downtime upgrade,
    but no suffix is ever duplicated.
    """
    base = (base_url or os.getenv("AI_BASE_URL", _DEFAULT_BASE_URL)).strip()
    base = base.rstrip("/")
    if base.endswith(_CHAT_COMPLETIONS_PATH):
        return base
    return base + _CHAT_COMPLETIONS_PATH


_INTERNAL_LINE_MARKERS = (
    "user safety:", "analysis", "metadata", "system information",
    "system prompt", "thinking", "thinking process", "the user asks:",
    "assistant analysis", "reasoning:",
)


def _clean_answer(content):
    """Remove provider/model internals before a group user can see them."""
    lines = []
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()
        normalized = line.lower().lstrip("#*- ").strip()
        if any(normalized.startswith(marker) for marker in _INTERNAL_LINE_MARKERS):
            continue
        # Some reasoning models prefix a final answer explicitly; retain only
        # the actual answer text after the label.
        if normalized.startswith("final:") or normalized.startswith("پاسخ نهایی:"):
            line = line.split(":", 1)[1].strip()
        if line:
            lines.append(line)
    answer = "\n".join(lines).strip()
    if not answer:
        raise AIServiceError("پاسخ سرویس فقط شامل اطلاعات داخلی بود.", kind="content")
    return answer


def _headers(api_key):
    """Standard OpenRouter attribution headers; values remain env-overridable."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("AI_HTTP_REFERER", _DEFAULT_HTTP_REFERER).strip() or _DEFAULT_HTTP_REFERER,
        "X-Title": os.getenv("AI_APP_TITLE", _DEFAULT_APP_TITLE).strip() or _DEFAULT_APP_TITLE,
    }


def _request(prompt):
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceError("کلید هوش مصنوعی تنظیم نشده است.", kind="config")
    url = endpoint_url()
    model = os.getenv("AI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    fallback = os.getenv("AI_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL).strip()
    try:
        max_tokens = max(1, int(os.getenv("AI_MAX_TOKENS", _DEFAULT_MAX_TOKENS)))
    except ValueError:
        max_tokens = _DEFAULT_MAX_TOKENS
    models = [model] + ([fallback] if fallback and fallback != model else [])
    last_error = None
    for index, selected_model in enumerate(models):
        response = _SESSION.post(
            url,
            headers=_headers(api_key),
            json={
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=_TIMEOUT,
        )
        if response.status_code >= 400:
            body = (response.text or "").strip().replace("\n", " ")[:2000]
            last_error = AIServiceError(
                f"OpenRouter/OpenAI-compatible HTTP {response.status_code} "
                f"endpoint={url} model={selected_model} response={body!r}",
                status_code=response.status_code, response_body=body,
                kind="forbidden" if response.status_code == 403 else "http"
            )
            # Shared free pools frequently return 429.  A single named
            # fallback keeps the reply useful without routing arbitrary models.
            if response.status_code == 429 and index + 1 < len(models):
                continue
            raise last_error
        try:
            data = response.json()
            provider_error = data.get("error") if isinstance(data, dict) else None
            if provider_error:
                provider_status = provider_error.get("code", response.status_code) if isinstance(provider_error, dict) else response.status_code
                body = (response.text or "").strip().replace("\n", " ")[:2000]
                last_error = AIServiceError(
                    f"OpenRouter provider error endpoint={url} model={selected_model} response={body!r}",
                    status_code=provider_status, response_body=body, kind="provider_error"
                )
                if index + 1 < len(models):
                    continue
                raise last_error
            content = data["choices"][0]["message"]["content"]
        except AIServiceError:
            raise
        except (ValueError, KeyError, IndexError, TypeError) as error:
            body = (response.text or "").strip().replace("\n", " ")[:2000]
            last_error = AIServiceError(
                f"OpenRouter/OpenAI-compatible invalid response endpoint={url} "
                f"model={selected_model} response={body!r}",
                status_code=response.status_code, response_body=body, kind="invalid_response"
            )
            if index + 1 < len(models):
                continue
            raise last_error from error
        return _clean_answer(content)
    raise last_error or AIServiceError("پاسخ سرویس هوش مصنوعی ناموفق بود.")


async def ask(prompt):
    """Run blocking HTTPS in a worker thread; never block the bot event loop."""
    try:
        return await asyncio.to_thread(_request, prompt)
    except AIServiceError:
        raise
    except requests.RequestException as error:
        kind = "timeout" if isinstance(error, requests.Timeout) else "transport"
        raise AIServiceError(
            f"OpenRouter/OpenAI-compatible {kind} error {error!r}", kind=kind
        ) from error
