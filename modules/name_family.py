"""Name & Family group state with a curated category-specific word database."""
import json
import random
import re
import time
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlencode, unquote, urlparse
from urllib.request import Request, urlopen

from modules.game_points import add
from modules.name_family_learning import learned_words, record as record_learning

LETTERS = (
    "ا", "ب", "پ", "ت", "ث", "ج", "چ", "ح", "خ", "د", "ذ", "ر", "ز", "ژ",
    "س", "ش", "ص", "ض", "ط", "ظ", "ع", "غ", "ف", "ق", "ک", "گ", "ل", "م",
    "ن", "و", "ه", "ی",
)
CATEGORIES = ("نام", "فامیل", "شهر", "میوه", "وسیله", "حیوان", "خواننده")
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "name_family_words.json"


def _normalize(value):
    """Unify Persian forms before category lookup without changing category meaning."""
    normalized = (
        str(value or "").strip().lower()
        .replace("ي", "ی").replace("ك", "ک").replace("آ", "ا")
        .replace("‌", "")
    )
    return " ".join(normalized.split())


def _load_valid_words():
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Name & Family word database is unavailable: {error}") from error
    if set(raw) != set(CATEGORIES):
        raise RuntimeError("Name & Family word database categories are invalid")
    valid = {}
    for category in CATEGORIES:
        words = raw[category]
        if not isinstance(words, list) or not all(isinstance(word, str) for word in words):
            raise RuntimeError(f"Name & Family database category is invalid: {category}")
        valid[category] = frozenset(words)
    return valid


# A versioned data file replaces the small hard-coded list. Answers remain category-specific.
VALID = _load_valid_words()
VALID_NORMALIZED = {
    category: frozenset(_normalize(answer) for answer in answers)
    for category, answers in VALID.items()
}
LEARNED_NORMALIZED = {
    category: set(learned_words().get(category, set()))
    for category in CATEGORIES
}


def _category_letters(category):
    return {
        normalized[0]
        for answer in VALID_NORMALIZED[category]
        if (normalized := _normalize(answer)) and normalized[0] in LETTERS
    }


CATEGORY_LETTERS = {category: _category_letters(category) for category in CATEGORIES}


def _distinct_round_answers(letter):
    """Find one unique valid answer per category, or declare the letter unplayable."""
    candidates = {
        category: tuple(
            sorted(
                answer for answer in VALID[category]
                if _normalize(answer).startswith(letter)
            )
        )
        for category in CATEGORIES
    }

    def choose(index, used, selected):
        if index == len(CATEGORIES):
            return tuple(selected)
        category = CATEGORIES[index]
        for answer in candidates[category]:
            normalized = _normalize(answer)
            if normalized not in used:
                result = choose(index + 1, used | {normalized}, selected + [answer])
                if result is not None:
                    return result
        return None

    return choose(0, set(), [])


def validate_database():
    """Classify every alphabet letter and reject a database with no complete rounds."""
    coverage = {
        letter: {
            category: letter in CATEGORY_LETTERS[category]
            for category in CATEGORIES
        }
        for letter in LETTERS
    }
    examples = {
        letter: _distinct_round_answers(letter)
        for letter in LETTERS
        if all(coverage[letter].values())
    }
    playable = tuple(letter for letter in LETTERS if examples.get(letter) is not None)
    if not playable:
        raise RuntimeError("Name & Family database has no fully covered playable letters")
    return coverage, examples, playable


# The runtime coverage check runs at import/startup, before a round can be built.
LETTER_COVERAGE, ROUND_EXAMPLES, PLAYABLE_LETTERS = validate_database()
UNPLAYABLE_LETTERS = tuple(letter for letter in LETTERS if letter not in PLAYABLE_LETTERS)

_INVALID_ANSWERS = frozenset({
    "نمیدونم", "نمی دونم", "نمی دانم", "نمیدانم", "ندارم", "هیچی", "نمیگم",
})
_VALID_TEXT = re.compile(r"^[آ-یءئؤة\s]+$")
# ---------------------------------------------------------------------------
# State for this game ONLY. Nothing here is shared with حدس پرچم، چیستان،
# جای خالی or any other game, so no other module can cancel, clear or
# overwrite a Name & Family round.
# ---------------------------------------------------------------------------
_ACTIVE = {}
_REMAINING_LETTERS = {}
_ROUND_SEQUENCE = 0
ROUND_SECONDS = 90

# Timer tasks owned exclusively by this game: chat_id -> asyncio.Task
_ROUND_TASKS = {}
# Rounds already finished, so results can never be produced twice.
_FINISHED_ROUNDS = set()

# Unknown answers are checked only after local database and learned-answer
# checks. The cache is process-local: no runtime data file is made.
_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKIPEDIA_API = "https://fa.wikipedia.org/w/api.php"
_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/"
_EXTERNAL_TIMEOUT_SECONDS = 2.0
_EXTERNAL_CACHE_SECONDS = 60 * 60
_EXTERNAL_CACHE = {}
_CATEGORY_TERMS = {
    "نام": ("given name", "first name", "forename", "personal name", "نام کوچک"),
    "فامیل": ("family name", "surname", "last name", "نام خانوادگی"),
    "شهر": ("city", "شهر"),
    "میوه": ("fruit", "میوه"),
    "وسیله": (
        "tool", "device", "appliance", "equipment", "instrument", "machine",
        "utensil", "ابزار", "وسیله", "دستگاه",
    ),
    "حیوان": (
        "animal", "mammal", "bird", "fish", "reptile", "amphibian", "insect",
        "جانور", "حیوان", "پستاندار", "پرنده", "ماهی", "خزنده", "دوزیست", "حشره",
    ),
    "خواننده": ("singer", "vocalist", "خواننده"),
}
_TRUSTED_WEB_HOSTS = frozenset({
    "fa.wikipedia.org", "en.wikipedia.org", "www.wikidata.org",
})


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    global _ROUND_SEQUENCE
    if chat_id in _ACTIVE:
        return None
    remaining = _REMAINING_LETTERS.get(chat_id)
    if not remaining:
        remaining = list(PLAYABLE_LETTERS)
        random.SystemRandom().shuffle(remaining)
        _REMAINING_LETTERS[chat_id] = remaining
    _ROUND_SEQUENCE += 1
    state = {
        "round_id": _ROUND_SEQUENCE,
        "letter": remaining.pop(),
        "answers": {},
        "started_at": time.monotonic(),
        "deadline": time.monotonic() + ROUND_SECONDS,
    }
    _ACTIVE[chat_id] = state
    return {
        "round_id": state["round_id"],
        "letter": state["letter"],
        "answers": {},
        "deadline": state["deadline"],
        "seconds": ROUND_SECONDS,
    }


def _parse_answers(text):
    """Accept the seven answer lines, tolerating real-keyboard whitespace.

    Mobile keyboards routinely append a trailing newline and users often leave
    a blank line between answers. Rejecting those silently dropped valid
    submissions, which is why answers "sometimes" were not recorded. Blank
    lines are ignored; category labels and legacy separators are still
    rejected.
    """
    raw_text = str(text or "")
    lines = [line.strip() for line in raw_text.splitlines()]
    parts = [line for line in lines if line]
    if len(parts) != len(CATEGORIES):
        return None
    # Reject legacy separators and category labels: they are not seven raw answers.
    for category, answer in zip(CATEGORIES, parts):
        normalized = _normalize(answer)
        label = _normalize(category)
        if "|" in answer or "،" in answer or normalized == label:
            return None
        if normalized.startswith(label) and normalized[len(label):].lstrip(":：- ") != normalized[len(label):]:
            return None
    return parts


def _validate_answer(category, letter, answer):
    """Returns True only for a real answer in the requested category."""
    normalized = _normalize(answer)
    if (
        len(normalized) < 2
        or not _VALID_TEXT.fullmatch(normalized)
        or normalized in _INVALID_ANSWERS
        or not normalized.startswith(_normalize(letter))
    ):
        return False
    return normalized in VALID_NORMALIZED[category]


def _category_terms_match(category, text):
    normalized_text = _normalize(re.sub(r"<.*?>", " ", unescape(str(text or ""))))
    return any(term in normalized_text for term in _CATEGORY_TERMS[category])


def _exact_match(value, normalized_answer):
    return _normalize(value) == normalized_answer


def _request_json(url, params):
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "SoroushPlusNameFamily/1.0",
        },
    )
    with urlopen(request, timeout=_EXTERNAL_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _wikidata_confirms_category(category, answer, normalized_answer):
    """Return the source name for an exact, category-matched Wikidata entity."""
    try:
        payload = _request_json(_WIKIDATA_API, {
            "action": "wbsearchentities",
            "search": answer,
            "language": "fa",
            "format": "json",
            "limit": 10,
        })
        for result in payload.get("search", []):
            match = result.get("match") or {}
            aliases = result.get("aliases") or ()
            exact = (
                _exact_match(match.get("text"), normalized_answer)
                or _exact_match(result.get("label"), normalized_answer)
                or any(_exact_match(alias, normalized_answer) for alias in aliases)
            )
            if exact and _category_terms_match(category, result.get("description")):
                return "wikidata"
    except (OSError, ValueError, TypeError):
        pass
    return None


def _wikipedia_confirms_category(category, answer, normalized_answer):
    """Return the source name for an exact title or redirect with matching context."""
    try:
        payload = _request_json(_WIKIPEDIA_API, {
            "action": "query",
            "titles": answer,
            "redirects": 1,
            "prop": "extracts|categories",
            "exintro": 1,
            "explaintext": 1,
            "cllimit": 50,
            "format": "json",
        })
        query = payload.get("query") or {}
        redirects = query.get("redirects") or ()
        is_exact_title = any(
            _exact_match(page.get("title"), normalized_answer)
            for page in (query.get("pages") or {}).values()
        )
        is_exact_redirect = any(
            _exact_match(item.get("from"), normalized_answer)
            for item in redirects
        )
        if not (is_exact_title or is_exact_redirect):
            return None
        for page in (query.get("pages") or {}).values():
            if page.get("missing") is not None:
                continue
            categories = " ".join(
                item.get("title", "") for item in page.get("categories", ())
            )
            context = " ".join((page.get("title", ""), page.get("extract", ""), categories))
            if _category_terms_match(category, context):
                return "wikipedia"
    except (OSError, ValueError, TypeError):
        pass
    return None


def _web_confirms_category(category, answer, normalized_answer):
    """Use web search only as a final fallback and only trust Wikimedia results."""
    try:
        request = Request(
            f"{_WEB_SEARCH_URL}?{urlencode({'q': f'\"{answer}\" {category}'})}",
            headers={
                "Accept": "text/html",
                "User-Agent": "SoroushPlusNameFamily/1.0",
            },
        )
        with urlopen(request, timeout=_EXTERNAL_TIMEOUT_SECONDS) as response:
            html = response.read().decode("utf-8", errors="replace")
        matches = re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for result in matches:
            link, title = result.groups()
            if "uddg=" in link:
                link = unquote(parse_qs(urlparse(link).query).get("uddg", [link])[0])
            if urlparse(link).netloc.lower() not in _TRUSTED_WEB_HOSTS:
                continue
            clean_title = re.sub(r"<.*?>", "", unescape(title)).strip()
            nearby = html[result.end():result.end() + 1200]
            snippet_match = re.search(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
                nearby,
                flags=re.IGNORECASE | re.DOTALL,
            )
            snippet = snippet_match.group(1) if snippet_match else ""
            if (
                _exact_match(clean_title, normalized_answer)
                and _category_terms_match(category, f"{clean_title} {snippet}")
            ):
                return "web"
    except (OSError, ValueError, TypeError):
        pass
    return None


def _external_confirms_category(category, answer, normalized_answer):
    """Try independent sources in order without trusting a failed lookup."""
    cache_key = (category, normalized_answer)
    cached = _EXTERNAL_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _EXTERNAL_CACHE_SECONDS:
        return cached[1]

    source = (
        _wikidata_confirms_category(category, answer, normalized_answer)
        or _wikipedia_confirms_category(category, answer, normalized_answer)
        or _web_confirms_category(category, answer, normalized_answer)
    )
    _EXTERNAL_CACHE[cache_key] = (now, source)
    return source


def _record_learning(
    category,
    letter,
    answer,
    normalized,
    chat_id,
    user_id,
    min_observations,
    min_unique_users,
    min_unique_chats,
):
    """Keep the existing confidence thresholds for every newly seen answer."""
    item = record_learning(
        category,
        letter,
        answer,
        normalized,
        chat_id,
        user_id,
        min_observations=min_observations,
        min_unique_users=min_unique_users,
        min_unique_chats=min_unique_chats,
    )
    if item.get("status") == "learned":
        LEARNED_NORMALIZED[category].add(normalized)
    return item


def _classify_answer(
    category,
    letter,
    answer,
    chat_id,
    user_id,
    seen_answers,
    learning_min_observations,
    learning_min_unique_users,
    learning_min_unique_chats,
):
    """Classify database, learned, learning, and invalid answers without heuristics."""
    normalized = _normalize(answer)
    duplicate = normalized in seen_answers
    seen_answers.add(normalized)
    if duplicate:
        return 0, "none", "duplicate", normalized
    if _validate_answer(category, letter, answer):
        return 10, "database", "database_match", normalized
    if normalized in LEARNED_NORMALIZED[category]:
        return 10, "learned", "learned_match", normalized

    # Only structurally valid answers with the selected letter enter learning memory.
    basic_valid = (
        len(normalized) >= 2
        and _VALID_TEXT.fullmatch(normalized)
        and normalized not in _INVALID_ANSWERS
        and normalized.startswith(_normalize(letter))
    )
    if not basic_valid:
        return 0, "none", "invalid", normalized

    # Wikidata is queried only for a structurally valid local miss. An exact
    # category-confirmed result receives this round's point immediately, while
    # still passing through the existing confidence-based learning pipeline.
    external_source = _external_confirms_category(category, answer, normalized)
    if external_source:
        _record_learning(
            category,
            letter,
            answer,
            normalized,
            chat_id,
            user_id,
            learning_min_observations,
            learning_min_unique_users,
            learning_min_unique_chats,
        )
        return 10, external_source, f"{external_source}_category_match", normalized

    item = _record_learning(
        category,
        letter,
        answer,
        normalized,
        chat_id,
        user_id,
        learning_min_observations,
        learning_min_unique_users,
        learning_min_unique_chats,
    )
    if item.get("status") == "learned":
        return 10, "learned", "auto_learned", normalized
    return 0, "learning", "insufficient_confidence", normalized


def _learning_threshold(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def submit(
    chat_id,
    user_id,
    name,
    text,
    logger=None,
    learning_min_observations=5,
    learning_min_unique_users=3,
    learning_min_unique_chats=2,
):
    state = _ACTIVE.get(chat_id)
    if not state:
        if logger is not None:
            logger.log_info(
                "NAME FAMILY TRACE SUBMIT_BLOCK "
                f"reason=no_active_round chat_id={chat_id} user_id={user_id}"
            )
        return None
    user_key = str(user_id)
    # A round accepts exactly one score per participant. This prevents the persistent
    # game score from being added twice while the round ranking is overwritten.
    existing = state["answers"].get(user_key)
    if existing is not None:
        # Do not signal a second successful submission or mutate persistent points.
        if logger is not None:
            logger.log_info(
                "NAME FAMILY TRACE SUBMIT_BLOCK "
                f"reason=duplicate_submission chat_id={chat_id} user_id={user_id}"
            )
        return None

    parts = _parse_answers(text)
    if parts is None:
        if logger is not None:
            logger.log_info(
                "NAME FAMILY TRACE SUBMIT_BLOCK "
                f"reason=parse_failed chat_id={chat_id} user_id={user_id} "
                f"line_count={len(str(text or '').splitlines())}"
            )
        return None
    if logger is not None:
        logger.log_info(
            "NAME FAMILY TRACE SUBMIT_PARSED "
            f"chat_id={chat_id} user_id={user_id} line_count={len(parts)}"
        )
    points = 0
    seen_answers = set()
    letter = state["letter"]
    min_observations = _learning_threshold(learning_min_observations, 5)
    min_unique_users = _learning_threshold(learning_min_unique_users, 3)
    min_unique_chats = _learning_threshold(learning_min_unique_chats, 2)
    for category, answer in zip(CATEGORIES, parts):
        score, source, reason, normalized = _classify_answer(
            category,
            letter,
            answer,
            chat_id,
            user_id,
            seen_answers,
            min_observations,
            min_unique_users,
            min_unique_chats,
        )
        points += score
        if logger is not None:
            logger.log_info(
                "NAME FAMILY VALIDATION "
                f"chat_id={chat_id} user_id={user_id} "
                f"category={category} raw_answer={answer} "
                f"normalized_answer={normalized} letter={letter} "
                f"source={source} reason={reason} "
                f"valid={source in {'database', 'learned', 'wikidata', 'wikipedia', 'web'}} score={score}"
            )
    state["answers"][user_key] = {
        "user_id": user_key,
        "name": name,
        "points": points,
        "round_id": state["round_id"],
    }
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id, round_id=None):
    """Close a round and return its ranking. Safe to call more than once.

    ``round_id`` guards against a stale timer from a previous round closing a
    freshly started one.
    """
    state = _ACTIVE.get(chat_id)
    if not state:
        return []
    if round_id is not None and state["round_id"] != round_id:
        return []
    if state["round_id"] in _FINISHED_ROUNDS:
        return []
    _ACTIVE.pop(chat_id, None)
    _FINISHED_ROUNDS.add(state["round_id"])
    if len(_FINISHED_ROUNDS) > 500:
        _FINISHED_ROUNDS.clear()
        _FINISHED_ROUNDS.add(state["round_id"])
    return sorted(
        state["answers"].values(),
        key=lambda item: item["points"],
        reverse=True,
    )


def cancel_round(chat_id):
    """Abort a round without producing results (admin disabling the bot)."""
    task = _ROUND_TASKS.pop(chat_id, None)
    if task is not None and not task.done():
        task.cancel()
    state = _ACTIVE.pop(chat_id, None)
    if state:
        _FINISHED_ROUNDS.add(state["round_id"])
    return bool(state)


def active_round_id(chat_id):
    state = _ACTIVE.get(chat_id)
    return state["round_id"] if state else None


def seconds_left(chat_id):
    state = _ACTIVE.get(chat_id)
    if not state:
        return 0
    return max(0.0, state["deadline"] - time.monotonic())


def reset_all():
    """Test helper: clear every Name & Family structure."""
    for task in list(_ROUND_TASKS.values()):
        if not task.done():
            task.cancel()
    _ROUND_TASKS.clear()
    _ACTIVE.clear()
    _FINISHED_ROUNDS.clear()
    _REMAINING_LETTERS.clear()


async def run_round(chat_id, round_id, on_results, logger=None, seconds=None):
    """Own the whole 90-second lifetime of one round.

    Results are delivered in a ``finally`` block, so they are sent even if the
    task is cancelled or ``on_results`` raises. This is what makes "results
    sometimes never appear" impossible.
    """
    import asyncio as _aio

    delay = ROUND_SECONDS if seconds is None else seconds
    cancelled = False
    try:
        await _aio.sleep(delay)
    except _aio.CancelledError:
        cancelled = True
        if logger is not None:
            logger.log_info(
                f"NAME FAMILY TIMER CANCELLED chat_id={chat_id} round_id={round_id} "
                "-> results will still be delivered"
            )
    finally:
        _ROUND_TASKS.pop(chat_id, None)
        if logger is not None:
            logger.log_info(
                f"NAME FAMILY TIMER END chat_id={chat_id} round_id={round_id} "
                f"cancelled={cancelled}"
            )
        state = _ACTIVE.get(chat_id)
        already_done = state is None or state["round_id"] != round_id
        if not already_done:
            ranking = finish(chat_id, round_id)
            if logger is not None:
                logger.log_info(
                    f"NAME FAMILY RESULTS START chat_id={chat_id} "
                    f"round_id={round_id} players={len(ranking)}"
                )
            try:
                await on_results(ranking)
                if logger is not None:
                    logger.log_info(
                        f"NAME FAMILY RESULTS SENT chat_id={chat_id} "
                        f"round_id={round_id} players={len(ranking)}"
                    )
            except Exception as error:
                if logger is not None:
                    logger.log_error(
                        f"NAME FAMILY RESULTS FAILED chat_id={chat_id} "
                        f"round_id={round_id} error={error!r}"
                    )
        if cancelled:
            raise _aio.CancelledError


def schedule_round(chat_id, round_id, on_results, logger=None, seconds=None):
    """Create and own the round timer task, replacing any stale one."""
    import asyncio as _aio

    previous = _ROUND_TASKS.pop(chat_id, None)
    if previous is not None and not previous.done():
        previous.cancel()
    try:
        loop = _aio.get_running_loop()
    except RuntimeError:
        return None
    task = loop.create_task(run_round(chat_id, round_id, on_results, logger, seconds))
    _ROUND_TASKS[chat_id] = task

    def _cleanup(done_task):
        if _ROUND_TASKS.get(chat_id) is done_task:
            _ROUND_TASKS.pop(chat_id, None)

    task.add_done_callback(_cleanup)
    return task
