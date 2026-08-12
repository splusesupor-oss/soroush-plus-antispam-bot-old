import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, ReadTimeout, RequestException
from urllib3.util.retry import Retry

FILE = Path("logs/search_cooldown.json")
SEARCH_UNAVAILABLE = "❌ ارتباط با سرور جستجو برقرار نشد، چند لحظه بعد دوباره تلاش کنید."
NO_RESULTS = "🔍 نتیجه‌ای پیدا نشد."


def can_search(user_id):
    FILE.parent.mkdir(exist_ok=True)
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    now = time.time()
    last = data.get(str(user_id), 0)
    if now - last < 60:
        return False, int(60 - (now - last))

    data[str(user_id)] = now
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, 0


def _search_session():
    """Session پایدار برای DuckDuckGo با سه تلاش روی خطاهای موقت اتصال."""
    retry = Retry(
        total=3,
        connect=0,
        read=0,
        status=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; SoroushPlusSearch/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    return session


def _extract_results(html):
    if not html or "<html" not in html.lower():
        return []
    matches = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    results = []
    for link, title in matches:
        title = re.sub(r"<.*?>", "", title).strip()
        if "uddg=" in link:
            try:
                link = unquote(parse_qs(urlparse(link).query).get("uddg", [link])[0])
            except (ValueError, TypeError):
                pass
        if title and link:
            results.append((title, link))
    return results


def search_web(query):
    query = (query or "").strip()
    if not query:
        return NO_RESULTS

    url = "https://html.duckduckgo.com/html/?q=" + quote(query)
    try:
        with _search_session() as session:
            response = None
            for attempt in range(3):
                try:
                    response = session.get(url, timeout=(10, 20))
                    break
                except (ConnectionError, ReadTimeout, ConnectionResetError):
                    if attempt == 2:
                        return SEARCH_UNAVAILABLE
                    time.sleep(1 if attempt == 0 else 2)
        if response.status_code >= 500 or response.status_code == 429:
            return SEARCH_UNAVAILABLE
        if response.status_code != 200:
            return NO_RESULTS
        results = _extract_results(response.text)
    except RequestException:
        return SEARCH_UNAVAILABLE
    except (ValueError, TypeError):
        return NO_RESULTS

    if not results:
        return NO_RESULTS

    output = "🔎 نتایج جستجو:\n\n"
    for index, (title, link) in enumerate(results[:5], 1):
        output += f"{index}- {title}\n🔗 {link}\n\n"
    return output


class FactualSearchError(RuntimeError):
    pass


_INTENT_MARKERS = (
    "?", "چیست", "چیه", "کجاست", "کیست", "کیه", "چگونه", "چطور", "چرا",
    "معرفی", "توضیح", "در مورد", "درباره", "چندتا", "چند مدل", "بهترین",
    "فرق", "تاریخ", "اطلاعات", "برنامه نویسی", "جستجو کن", "سرچ کن",
)
_INTENT_FILLERS = re.compile(r"^(?:لطفاً|لطفا|میشه|می شه|میتونی|می تونی|جستجو کن|سرچ کن|در مورد|درباره|چندتا|چند مدل)\s+|\s+(?:توضیح بده|معرفی کن|بگو|رو بگو|رو سرچ کن)$")


def factual_intent(text):
    """Return (is_information_request, focused_topic) from natural Persian text."""
    value = " ".join(str(text or "").strip().split())
    normalized = value.replace("؟", "?").lower()
    if len(value) < 3 or normalized in {"سلام", "خوبی", "چه خبر", "عجب", "مرسی", "ممنون"}:
        return False, ""
    is_request = any(marker in normalized for marker in _INTENT_MARKERS) or len(value) >= 12
    if not is_request:
        return False, ""
    topic = _INTENT_FILLERS.sub("", value).strip(" ؟?،")
    return True, topic or value


def _clean_factual_text(value):
    value = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", str(value or ""))
    value = value.replace("\u200c", "‌")
    value = re.sub(r"\s+([،؛:,.!?؟])", r"\1", value)
    value = re.sub(r"([،؛:,.!?؟])(?=\S)", r"\1 ", value)
    return " ".join(value.split())


def _extract_factual_results(html):
    """Read title/snippet pairs for factual summaries; do not expose links."""
    if not html or "<html" not in html.lower():
        return []
    blocks = re.findall(r'<div class="result[^>]*>.*?</div>\s*</div>', html, re.I | re.S)
    results = []
    for block in blocks:
        title_match = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.I | re.S)
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, re.I | re.S)
        title = re.sub(r"<.*?>", "", title_match.group(1)).strip() if title_match else ""
        snippet = re.sub(r"<.*?>", "", snippet_match.group(1)).strip() if snippet_match else ""
        if title and snippet:
            results.append((title, snippet))
    # Fallback pairing for DuckDuckGo markup variants.
    if not results:
        titles = [re.sub(r"<.*?>", "", value).strip() for value in re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.I | re.S)]
        snippets = [re.sub(r"<.*?>", "", value).strip() for value in re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', html, re.I | re.S)]
        results = [(title, snippets[index]) for index, title in enumerate(titles) if title and index < len(snippets) and snippets[index]]
    return results


def _factual_text(results):
    if not results:
        return None
    # Two independent snippets are enough for a short response without
    # dumping raw search links. Source titles are retained as provenance only.
    facts = []
    titles = []
    seen = set()
    for title, snippet in results[:5]:
        snippet = _clean_factual_text(snippet)[:420]
        marker = re.sub(r"\W+", "", snippet.lower())
        if not snippet or marker in seen:
            continue
        seen.add(marker)
        facts.append(snippet)
        titles.append(_clean_factual_text(title))
        if len(facts) == 2:
            break
    if not facts:
        return None
    return "\n\n".join(facts) + "\n\nمنابع: " + " | ".join(titles)


def search_factual(query):
    """DuckDuckGo factual summary; public ``جستجو`` output remains unchanged."""
    query = (query or "").strip()
    if not query:
        raise FactualSearchError("no_results")
    url = "https://html.duckduckgo.com/html/?q=" + quote(query)
    try:
        with _search_session() as session:
            response = session.get(url, timeout=(10, 20))
    except (ConnectionError, ReadTimeout, ConnectionResetError, RequestException) as error:
        raise FactualSearchError("unavailable") from error
    if response.status_code != 200:
        raise FactualSearchError("unavailable" if response.status_code >= 500 or response.status_code == 429 else "no_results")
    answer = _factual_text(_extract_factual_results(response.text))
    if not answer:
        raise FactualSearchError("no_results")
    return answer
