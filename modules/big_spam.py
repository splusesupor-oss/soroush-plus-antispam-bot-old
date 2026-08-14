"""Early Big Spam detection and delete-batch sizing.

Pure helpers: no client, no queue, no moderation policy besides detection.

Two detection paths stay separate:

* Intra-message Big Spam — a single payload packed with the same stem/phrase.
* Multi-message promotional wave — several clearly promotional messages that
  collapse to the same campaign after normalization.

Raw text is never the comparison key. IDs still come from the tracker rows.
"""
import re
from collections import Counter
from difflib import SequenceMatcher

REPEAT_WINDOW_SECONDS = 60
SIMILAR_MESSAGE_THRESHOLD = 2
WAVE_SHORT_THRESHOLD = 4
PHRASE_REPEAT_THRESHOLD = 6  # more than 5 meaningful phrases
PACKED_TOKEN_THRESHOLD = 6
LARGE_PAYLOAD_CHARS = 120
DELETE_BATCH_MAX = 100

_AD_MARKERS = (
    "بیو چک",
    "چک بیو",
    "بیوچک",
    "بیا پیوی",
    "بیا پی وی",
    "بیا پیویم",
    "فیلم گذاشتم",
    "فیلم گذاشتم بیوم",
    "عضو شو",
    "جوین شو",
    "جوین کانال",
    "اد پیوی",
    "اد پی وی",
    "پیوی پیام",
)

_COMPACT_STEMS = (
    "بیوچک",
    "چکبیو",
    "بیاپیوی",
    "بیاپیویم",
    "بیاگروه",
    "بیاچنل",
    "بیاکانال",
    "فالوکن",
    "فولوکن",
    "جوینشو",
    "جوینکن",
    "جوینکانال",
    "عضوشو",
    "فیلمگذاشتم",
    "فیلمدارم",
    "ادپیوی",
    "تادیرنشده",
    "بکوب",
)

_PROMO_RE = re.compile(
    r"بیو\s*چک|چک\s*بیو|"
    r"بیا\s*پی\s*وی|"
    r"بیا\s*(?:گروه|چنل|کانال|پیویم)|"
    r"فالو\s*کن|فولو\s*کن|"
    r"(?:جوین|عضو)\s*(?:شو|کن|کانال)|"
    r"فیلم\s*(?:گذاشتم|دارم|جدید)|"
    r"اد\s*پی\s*وی|"
    r"تا\s*دیر\s*نشده|بکوب"
)

_TRANSLATE = str.maketrans({
    "ي": "ی",
    "ى": "ی",
    "ئ": "ی",
    "ك": "ک",
    "ة": "ه",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ؤ": "و",
    "\u0640": "",
    "\u200c": " ",
    "\u200d": " ",
    "\u200f": "",
    "\u200e": "",
    "\u202a": "",
    "\u202b": "",
    "\u202c": "",
    "\u202d": "",
    "\u202e": "",
    "\u064b": "",
    "\u064c": "",
    "\u064d": "",
    "\u064e": "",
    "\u064f": "",
    "\u0650": "",
    "\u0651": "",
    "\u0652": "",
    "\u0653": "",
    "\u0654": "",
    "\u0655": "",
    "\ufe0f": "",
    "\ufe0e": "",
})

_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_REPEAT_RE = re.compile(r"(.)\1+", re.UNICODE)
_TOKEN_RE = re.compile(r"[\wآ-ی]+", re.UNICODE)

_SHORT_CHAT = frozenset({
    "سلام", "سللام", "خوبی", "خوبین", "چطوری", "ممنون", "مرسی",
    "باشه", "آره", "اره", "نه", "خیلی", "اوکی", "ok", "صبح",
    "بخیر", "شب", "خداحافظ",
})


def normalize_text(text):
    """Stable comparison form: drop decorations, collapse stretched letters."""
    value = str(text or "").translate(_TRANSLATE).lower()
    value = _NON_WORD_RE.sub(" ", value)
    value = _REPEAT_RE.sub(r"\1", value)
    return " ".join(value.split())


def compact_text(text):
    return re.sub(r"\s+", "", normalize_text(text))


def tokens(text):
    return _TOKEN_RE.findall(normalize_text(text))


def is_contentful(text):
    """Skip greetings and single-word chatter; keep real repeated campaigns."""
    toks = tokens(text)
    distinct = [token for token in dict.fromkeys(toks)]
    if not distinct:
        return False
    if looks_promotional(text) and (len(distinct) >= 2 or len(compact_text(text)) >= 6):
        return True
    if len(distinct) < 2:
        return False
    if len(toks) <= 2 and all(token in _SHORT_CHAT or len(token) <= 2 for token in distinct):
        return False
    compact = compact_text(text)
    if len(toks) >= 3 and len(compact) >= 8:
        return True
    if len(distinct) >= 2 and len(compact) >= 14:
        return True
    return False


def looks_promotional(text):
    normalized = normalize_text(text)
    if not normalized:
        return False
    compact = compact_text(normalized)
    for marker in _AD_MARKERS:
        cooked = normalize_text(marker)
        if cooked and (cooked in normalized or cooked.replace(" ", "") in compact):
            return True
    if _PROMO_RE.search(normalized):
        return True
    return any(stem and stem in compact for stem in _COMPACT_STEMS)


def markers_in(text):
    normalized = normalize_text(text)
    compact = compact_text(normalized)
    found = []
    for marker in _AD_MARKERS:
        cooked = normalize_text(marker)
        if cooked and (cooked in normalized or cooked.replace(" ", "") in compact):
            found.append(marker)
    return found


def _usable_token(token):
    return token not in _SHORT_CHAT and len(token) >= 3


def max_token_repeats(text):
    """Most-repeated non-chat token inside one message."""
    counts = Counter(token for token in tokens(text) if _usable_token(token))
    return max(counts.values()) if counts else 0


def max_phrase_repeats(text):
    """Count the most-repeated 2–5 token phrase in one message."""
    toks = tokens(text)
    if len(toks) < 2:
        return 0
    highest = 0
    for size in (2, 3, 4, 5):
        if len(toks) < size:
            break
        counts = Counter()
        for index in range(len(toks) - size + 1):
            piece = toks[index:index + size]
            if len(set(piece)) < 2:
                continue
            if all(part in _SHORT_CHAT for part in piece):
                continue
            if sum(len(token) for token in piece) < 4:
                continue
            counts[" ".join(piece)] += 1
        if counts:
            highest = max(highest, max(counts.values()))
    return highest


def max_compact_repeats(text):
    """Catch packed stems even when the sender omitted spaces."""
    toks = tokens(text)
    if toks and all(token in _SHORT_CHAT for token in toks):
        return 0
    compact = compact_text(text)
    length = len(compact)
    if length < 9:
        return 0
    highest = 0
    seen = set(toks)
    for token in seen:
        if _usable_token(token):
            highest = max(highest, compact.count(token))
    limit = min(16, length // 2)
    for size in range(3, limit + 1):
        for offset in range(size):
            piece = compact[offset:offset + size]
            if len(piece) < 3 or piece in _SHORT_CHAT or piece in seen:
                continue
            if not _TOKEN_RE.fullmatch(piece):
                continue
            highest = max(highest, compact.count(piece))
        if highest >= PACKED_TOKEN_THRESHOLD:
            return highest
    return highest


def intra_message_spam(text):
    """True only when one payload itself is a packed repeat."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if max_token_repeats(raw) >= PACKED_TOKEN_THRESHOLD:
        return True
    if max_phrase_repeats(raw) >= PHRASE_REPEAT_THRESHOLD:
        return True
    if max_compact_repeats(raw) >= PACKED_TOKEN_THRESHOLD:
        return True
    return False


def _ngrams(toks, size):
    return {" ".join(toks[index:index + size]) for index in range(len(toks) - size + 1)}


def shares_phrase(left, right):
    """True when two texts share a consecutive 2–4 word phrase."""
    first = tokens(left)
    second = tokens(right)
    for size in (4, 3, 2):
        if len(first) < size or len(second) < size:
            continue
        shared = _ngrams(first, size) & _ngrams(second, size)
        if not shared:
            continue
        if size >= 3:
            return True
        for phrase in shared:
            parts = phrase.split()
            if len(set(parts)) < 2:
                continue
            if all(part in _SHORT_CHAT for part in parts):
                continue
            return True
    return False


def similarity_score(left, right):
    """0..1 similarity on the normalized form only."""
    first = normalize_text(left)
    second = normalize_text(right)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    compact_first = first.replace(" ", "")
    compact_second = second.replace(" ", "")
    if compact_first == compact_second:
        return 1.0
    if first in second or second in first:
        shorter = first if len(first) <= len(second) else second
        longer = second if shorter is first else first
        return len(shorter) / max(len(longer), 1)
    if compact_first in compact_second or compact_second in compact_first:
        shorter = compact_first if len(compact_first) <= len(compact_second) else compact_second
        longer = compact_second if shorter is compact_first else compact_first
        return len(shorter) / max(len(longer), 1)
    return max(
        SequenceMatcher(None, first, second).ratio(),
        SequenceMatcher(None, compact_first, compact_second).ratio(),
    )


def similar_promotional(left, right):
    """True when two promotional texts are clearly the same campaign."""
    if not looks_promotional(left) or not looks_promotional(right):
        return False
    first = normalize_text(left)
    second = normalize_text(right)
    if not first or not second:
        return False
    if first == second or compact_text(first) == compact_text(second):
        return True
    score = similarity_score(left, right)
    if score >= 0.72:
        return True
    if shares_phrase(left, right):
        return True
    if set(markers_in(left)) & set(markers_in(right)):
        return True
    compact_first = compact_text(first)
    compact_second = compact_text(second)
    if (
        compact_first and compact_second
        and min(len(compact_first), len(compact_second)) >= 5
        and (compact_first in compact_second or compact_second in compact_first)
    ):
        return True
    return False


def similar_repeat(left, right):
    """Legacy helper: same campaign after normalization.

    Multi-message Big Spam no longer uses this for ordinary chat. Promotional
    waves go through ``similar_promotional`` instead.
    """
    if not is_contentful(left) or not is_contentful(right):
        return False
    score = similarity_score(left, right)
    if score >= 0.78:
        return True
    if score >= 0.52 and shares_phrase(left, right):
        return True
    return False


def is_strong_promotional(text):
    """Multi-word / packed ads can start a wave on the second copy."""
    if not looks_promotional(text):
        return False
    toks = tokens(text)
    compact = compact_text(text)
    if len(toks) >= 2:
        return True
    if len(compact) >= 10:
        return True
    promo_hits = sum(1 for token in toks if looks_promotional(token))
    if promo_hits >= 2:
        return True
    if any(compact.count(stem) >= 2 for stem in _COMPACT_STEMS):
        return True
    return False


def wave_needed(text):
    """How many similar promotional messages are required, or None."""
    if not looks_promotional(text):
        return None
    if is_strong_promotional(text):
        return SIMILAR_MESSAGE_THRESHOLD
    return WAVE_SHORT_THRESHOLD


def _row_ids(rows):
    return {
        row.get("message_id") for row in rows
        if isinstance(row.get("message_id"), int) and row["message_id"] > 0
    }


def detect_big_spam(text, recent_rows, *, now=None):
    """Return ``(is_big, reason, ids)`` from the current text and tracker rows.

    ``recent_rows`` should already include the current message. On a hit the
    IDs are every in-window tracker row for this caller-scoped user, not only
    the rows the detector matched exactly.
    """
    raw = str(text or "").strip()
    if not raw:
        return False, "", set()

    window = REPEAT_WINDOW_SECONDS
    stamp = time_now(now)
    in_window = [
        row for row in recent_rows
        if (stamp - float(row.get("timestamp", stamp))) <= window
    ]

    if intra_message_spam(raw):
        return True, "repeated_promotional_phrase", _row_ids(in_window or recent_rows)

    needed = wave_needed(raw)
    if needed is not None:
        promo = [
            row for row in in_window
            if similar_promotional(raw, row.get("text", ""))
        ]
        if len(promo) >= needed:
            return True, "repeated_promotional_messages", _row_ids(in_window)

    return False, "", set()


def time_now(now=None):
    import time
    return time.time() if now is None else now


def chunk_ids(message_ids, batch_size=DELETE_BATCH_MAX):
    """Split IDs into immediate batches. Size is a max, never a start gate."""
    pending = sorted({
        message_id for message_id in message_ids
        if isinstance(message_id, int) and message_id > 0
    })
    if not pending:
        return []
    size = max(int(batch_size), 1)
    return [pending[index:index + size] for index in range(0, len(pending), size)]
