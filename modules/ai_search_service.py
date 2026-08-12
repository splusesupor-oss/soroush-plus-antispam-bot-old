"""Search-backed textual assistant without an external generative-AI provider."""
import re
from html import unescape
from urllib.parse import quote

import requests

_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; SoroushPlusBot/1.0; +https://github.com/splusesupor-oss/soroush-plus-antispam-bot-old)",
    "Accept-Language": "fa,en;q=0.8",
})


class SearchAssistantError(RuntimeError):
    pass


def looks_information_seeking(text):
    """Avoid searching greetings/chatter while accepting natural knowledge asks."""
    value = " ".join(str(text or "").strip().split())
    if len(value) < 3:
        return False
    normalized = value.replace("؟", "?").lower()
    small_talk = {"سلام", "سلام!", "سلام؟", "خوبی", "حالت چطوره", "چه خبر", "مرسی", "ممنون"}
    if normalized in small_talk:
        return False
    markers = (
        "?", "چیست", "چیه", "کجاست", "کیست", "کیه", "چرا", "چطور",
        "چگونه", "بهترین", "معنی", "معرفی", "توضیح", "اطلاعات", "فرق",
        "تاریخ", "قیمت", "نحوه", "روش", "آموزش", "کمک",
    )
    return any(marker in normalized for marker in markers) or len(value) >= 18


def _clean_html(value):
    value = re.sub(r"<.*?>", " ", value or "")
    return " ".join(unescape(value).split())


_QUERY_STOPWORDS = {"چیست", "چیه", "کجاست", "کیست", "کیه", "چرا", "چطور", "چگونه", "بهترین", "اطلاعات", "درباره", "برای", "است", "هست", "را", "های", "ها"}


def _answer_from_results(results, query):
    if not results:
        return None
    tokens = {
        token.lower() for token in re.findall(r"[A-Za-zآ-ی]{3,}", query or "")
        if token.lower() not in _QUERY_STOPWORDS
    }
    ranked = []
    for title, snippet in results:
        haystack = f"{title} {snippet}".lower()
        score = sum(token in haystack for token in tokens)
        if score:
            ranked.append((score, title, snippet))
    if not ranked:
        return None
    _, title, snippet = max(ranked, key=lambda item: item[0])
    snippet = snippet[:700].strip()
    return f"{snippet}\n\nمنبع: {title}" if snippet else None


def _google_custom_search(query):
    """Use official Google Custom Search when local API credentials exist."""
    import os
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    search_cx = os.getenv("GOOGLE_SEARCH_CX", "").strip()
    if not api_key or not search_cx:
        return None
    try:
        response = _SESSION.get(
            _GOOGLE_CSE_URL,
            params={"key": api_key, "cx": search_cx, "q": query, "hl": "fa"},
            timeout=(4, 12),
        )
    except requests.Timeout as error:
        raise SearchAssistantError("google_timeout") from error
    except requests.RequestException as error:
        raise SearchAssistantError("google_transport") from error
    if response.status_code != 200:
        raise SearchAssistantError(f"google_http_{response.status_code}")
    try:
        data = response.json()
        results = [(str(item.get("title") or ""), str(item.get("snippet") or ""))
                   for item in data.get("items", [])]
    except (ValueError, TypeError, AttributeError) as error:
        raise SearchAssistantError("google_invalid_response") from error
    return _answer_from_results(results, query)


def search_answer(query):
    """Use Google Search proper: official Google Custom Search JSON API only."""
    query = " ".join(str(query or "").strip().split())
    if not query:
        raise SearchAssistantError("no_results")
    answer = _google_custom_search(query)
    if answer:
        return answer
    # No scraping or Gemini/Google-AI fallback is used.  Operators must set
    # GOOGLE_API_KEY and GOOGLE_SEARCH_CX for official Google Search access.
    raise SearchAssistantError("google_search_not_configured_or_no_results")
