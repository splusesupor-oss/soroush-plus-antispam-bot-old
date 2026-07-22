
import json
import time
from pathlib import Path
import requests
from urllib.parse import quote

FILE = Path("logs/search_cooldown.json")

def can_search(user_id):
    FILE.parent.mkdir(exist_ok=True)
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except:
        data = {}

    now = time.time()
    last = data.get(str(user_id), 0)

    if now - last < 60:
        return False, int(60 - (now-last))

    data[str(user_id)] = now
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, 0


def search_web(query):
    try:
        url = "https://html.duckduckgo.com/html/?q=" + quote(query)
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })

        text = r.text

        import re
        results = re.findall(
            r'nofollow" class="result__a" href="(.*?)".*?>(.*?)</a>',
            text
        )

        if not results:
            return "❌ نتیجه‌ای پیدا نشد"

        out = "🔎 نتایج جستجو:\n\n"
        from urllib.parse import unquote, urlparse, parse_qs

        for i, (link, title) in enumerate(results[:5], 1):
            title = re.sub("<.*?>", "", title)

            if "uddg=" in link:
                try:
                    link = parse_qs(urlparse(link).query).get("uddg", [link])[0]
                    link = unquote(link)
                except:
                    pass

            out += f"{i}- {title}\n🔗 {link}\n\n"

        return out

    except Exception as e:
        return f"❌ خطا در جستجو: {e}"
