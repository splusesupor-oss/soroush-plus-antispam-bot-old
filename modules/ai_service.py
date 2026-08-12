"""Async OpenAI-compatible text API client; no group policy is kept here."""
import asyncio
import os

import requests

_DEFAULT_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_TIMEOUT = (5, 30)
_SESSION = requests.Session()


class AIServiceError(RuntimeError):
    pass


def _request(prompt):
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceError("کلید هوش مصنوعی تنظیم نشده است.")
    url = os.getenv("AI_BASE_URL", _DEFAULT_URL).strip() or _DEFAULT_URL
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
        raise AIServiceError(f"خطای سرویس هوش مصنوعی ({response.status_code})")
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise AIServiceError("پاسخ سرویس هوش مصنوعی معتبر نیست.") from error
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
        raise AIServiceError("ارتباط با سرویس هوش مصنوعی ناموفق بود.") from error
