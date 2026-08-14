"""Early Big Spam detection and delete-batch sizing.

Pure helpers: no client, no queue, no moderation policy besides detection.
"""
import re
from collections import Counter

REPEAT_WINDOW_SECONDS = 60
SIMILAR_MESSAGE_THRESHOLD = 2
PHRASE_REPEAT_THRESHOLD = 6  # more than 5 meaningful phrases
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

_TRANSLATE = str.maketrans({
    "ي": "ی",
    "ك": "ک",
    "\u200c": " ",
    "\u200d": " ",
    "\u200f": "",
    "\u200e": "",
})


def normalize_text(text):
    value = str(text or "").translate(_TRANSLATE).lower()
    return " ".join(value.split())


def compact_text(text):
    return re.sub(r"\s+", "", normalize_text(text))


def tokens(text):
    return re.findall(r"[\wآ-ی]+", normalize_text(text))


_SHORT_CHAT = frozenset({
    "سلام", "سللام", "خوبی", "خوبین", "چطوری", "ممنون", "مرسی",
    "باشه", "آره", "اره", "نه", "خیلی", "اوکی", "ok", "صبح",
    "بخیر", "شب", "خداحافظ",
})


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
        if marker in normalized or marker.replace(" ", "") in compact:
            return True
    return False


def markers_in(text):
    normalized = normalize_text(text)
    compact = compact_text(normalized)
    found = []
    for marker in _AD_MARKERS:
        if marker in normalized or marker.replace(" ", "") in compact:
            found.append(marker)
    return found


def max_phrase_repeats(text):
    """Count the most-repeated 2–5 token phrase in one message."""
    tokens = re.findall(r"[\wآ-ی]+", normalize_text(text))
    if len(tokens) < 2:
        return 0
    highest = 0
    for size in (2, 3, 4, 5):
        if len(tokens) < size:
            break
        counts = Counter()
        for index in range(len(tokens) - size + 1):
            piece = tokens[index:index + size]
            if len(set(piece)) < 2:
                continue
            if sum(len(token) for token in piece) < 4:
                continue
            counts[" ".join(piece)] += 1
        if counts:
            highest = max(highest, max(counts.values()))
    return highest


def similar_promotional(left, right):
    """True when two promotional texts are clearly the same campaign."""
    first = normalize_text(left)
    second = normalize_text(right)
    if not first or not second:
        return False
    if not looks_promotional(first) or not looks_promotional(second):
        return False
    if first == second:
        return True
    if len(first) >= 6 and len(second) >= 6 and (first in second or second in first):
        return True
    return bool(set(markers_in(first)) & set(markers_in(second)))


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
    """0..1 similarity: exact, containment, then sequence ratio."""
    from difflib import SequenceMatcher
    first = normalize_text(left)
    second = normalize_text(right)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    if first in second or second in first:
        shorter = first if len(first) <= len(second) else second
        longer = second if shorter is first else first
        return len(shorter) / max(len(longer), 1)
    return SequenceMatcher(None, first, second).ratio()


def similar_repeat(left, right):
    """Same spam campaign even if the wording shifted a little."""
    if not is_contentful(left) or not is_contentful(right):
        return False
    score = similarity_score(left, right)
    if score >= 0.78:
        return True
    if score >= 0.52 and shares_phrase(left, right):
        return True
    return False


def _row_ids(rows):
    return {
        row.get("message_id") for row in rows
        if isinstance(row.get("message_id"), int) and row["message_id"] > 0
    }


def detect_big_spam(text, recent_rows, *, now=None):
    """Return ``(is_big, reason, ids)`` from the current text and tracker rows.

    ``recent_rows`` should already include the current message.
    """
    raw = str(text or "").strip()
    if not raw:
        return False, "", set()

    if max_phrase_repeats(raw) >= PHRASE_REPEAT_THRESHOLD:
        return True, "repeated_promotional_phrase", _row_ids(recent_rows)

    window = REPEAT_WINDOW_SECONDS
    stamp = time_now(now)
    in_window = [
        row for row in recent_rows
        if (stamp - float(row.get("timestamp", stamp))) <= window
    ]
    compact = compact_text(raw)

    matching = [
        row for row in in_window
        if similar_repeat(raw, row.get("text", ""))
    ]
    if len(matching) >= SIMILAR_MESSAGE_THRESHOLD:
        return True, "repeated_similar_messages", _row_ids(matching)

    if looks_promotional(raw):
        promo = [
            row for row in in_window
            if similar_promotional(raw, row.get("text", ""))
        ]
        if len(promo) >= SIMILAR_MESSAGE_THRESHOLD:
            return True, "repeated_promotional_messages", _row_ids(promo)

    if len(compact) >= LARGE_PAYLOAD_CHARS:
        matching = [
            row for row in in_window
            if compact_text(row.get("text", "")) == compact
            and len(compact_text(row.get("text", ""))) >= LARGE_PAYLOAD_CHARS
        ]
        if len(matching) >= SIMILAR_MESSAGE_THRESHOLD:
            return True, "rapid_repeated_large_messages", _row_ids(matching)

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
