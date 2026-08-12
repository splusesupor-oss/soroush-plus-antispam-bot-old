"""Search-backed textual assistant without an external generative-AI provider."""
import re
from html import unescape
from urllib.parse import quote

import requests

_SEARCH_URL = "https://www.google.com/search?q={query}&hl=fa"
_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_BING_URL = "https://www.bing.com/search?q={query}"
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


def _extract_google(html):
    # Google markup changes often. h3 titles plus nearby visible snippet text
    # are enough for a concise cited answer and do not expose raw result pages.
    titles = [_clean_html(value) for value in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.I | re.S)]
    snippets = [_clean_html(value) for value in re.findall(r"<div[^>]+data-sncf[^>]*>(.*?)</div>", html, re.I | re.S)]
    if not snippets:
        snippets = [_clean_html(value) for value in re.findall(r"<div class=\"(?:VwiC3b|IsZvec)[^\"]*\"[^>]*>(.*?)</div>", html, re.I | re.S)]
    pairs = []
    for index, title in enumerate(titles):
        snippet = snippets[index] if index < len(snippets) else ""
        if title and snippet:
            pairs.append((title, snippet))
    return pairs


def _extract_bing(html):
    blocks = re.findall(r'<li class="b_algo".*?</li>', html or "", re.I | re.S)
    results = []
    for block in blocks:
        title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h2>', block, re.I | re.S)
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.I | re.S)
        title = _clean_html(title_match.group(1)) if title_match else ""
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
        if title and snippet:
            results.append((title, snippet))
    return results


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
    """Return a short evidence-backed answer, never raw Google result links."""
    official_answer = _google_custom_search(query)
    if official_answer:
        return official_answer

    url = _SEARCH_URL.format(query=quote(query))
    try:
        response = _SESSION.get(url, timeout=(4, 12))
    except requests.Timeout as error:
        raise SearchAssistantError("timeout") from error
    except requests.RequestException as error:
        raise SearchAssistantError("transport") from error
    if response.status_code == 200:
        answer = _answer_from_results(_extract_google(response.text), query)
        if answer:
            return answer

    # Google sometimes returns a JavaScript-only consent/challenge page to a
    # server-side bot.  Keep Google as the primary lookup, then use a public
    # HTML fallback so the allowed user still receives evidence-backed text.
    try:
        fallback = _SESSION.get(_BING_URL.format(query=quote(query)), timeout=(4, 12))
    except requests.Timeout as error:
        raise SearchAssistantError("timeout") from error
    except requests.RequestException as error:
        raise SearchAssistantError("transport") from error
    if fallback.status_code != 200:
        raise SearchAssistantError(f"http_{fallback.status_code}")
    answer = _answer_from_results(_extract_bing(fallback.text), query)
    if not answer:
        raise SearchAssistantError("no_results")
    return answer
