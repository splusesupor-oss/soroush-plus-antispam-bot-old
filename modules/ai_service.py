"""Async OpenAI-compatible text API client; no group policy is kept here."""
import asyncio
import os

import requests

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_CHAT_COMPLETIONS_PATH = "/chat/completions"
_DEFAULT_MODEL = "openrouter/free"
_TIMEOUT = (5, 30)
_SESSION = requests.Session()


class AIServiceError(RuntimeError):
    pass


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


def _request(prompt):
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceError("کلید هوش مصنوعی تنظیم نشده است.")
    url = endpoint_url()
    model = os.getenv("AI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    response = _SESSION.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "به فارسی، کوتاه، مفید و مودب پاسخ بده."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        },
        timeout=_TIMEOUT,
    )
    if response.status_code >= 400:
        # This detail is propagated only to the bot logger by the caller; the
        # user-facing handler keeps its short generic error message.
        body = (response.text or "").strip().replace("\n", " ")[:2000]
        raise AIServiceError(
            f"OpenRouter/OpenAI-compatible HTTP {response.status_code} "
            f"endpoint={url} model={model} response={body!r}"
        )
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        body = (response.text or "").strip().replace("\n", " ")[:2000]
        raise AIServiceError(
            f"OpenRouter/OpenAI-compatible invalid response endpoint={url} "
            f"model={model} response={body!r}"
        ) from error
    content = str(content or "").strip()
    if not content:
        raise AIServiceError("پاسخ سرویس هوش مصنوعی خالی است.")
    return content


async def ask(prompt):
    """Run blocking HTTPS in a worker thread; never block the bot event loop."""
    try:
        return await asyncio.to_thread(_request, prompt)
    except AIServiceError:
        raise
    except requests.RequestException as error:
        raise AIServiceError(
            f"OpenRouter/OpenAI-compatible transport error {error!r}"
        ) from error
