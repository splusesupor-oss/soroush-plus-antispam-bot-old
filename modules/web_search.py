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
