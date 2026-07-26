"""Name & Family group state with a curated category-specific word database."""
import json
import random
import re
from pathlib import Path

from modules.game_points import add

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
_ACTIVE = {}
_REMAINING_LETTERS = {}
_ROUND_SEQUENCE = 0


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
    }
    _ACTIVE[chat_id] = state
    return {"round_id": state["round_id"], "letter": state["letter"], "answers": {}}


def _parse_answers(text):
    """Accept only the exact seven raw answer lines requested by the game."""
    raw_text = str(text or "")
    if raw_text.endswith(("\n", "\r")):
        return None
    lines = raw_text.splitlines()
    if len(lines) != len(CATEGORIES):
        return None
    parts = [line.strip() for line in lines]
    if any(not part for part in parts):
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


def submit(chat_id, user_id, name, text, logger=None):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    user_key = str(user_id)
    # A round accepts exactly one score per participant. This prevents the persistent
    # game score from being added twice while the round ranking is overwritten.
    existing = state["answers"].get(user_key)
    if existing is not None:
        # Do not signal a second successful submission or mutate persistent points.
        return None

    parts = _parse_answers(text)
    if parts is None:
        return None
    valid_parts = 0
    seen_answers = set()
    letter = state["letter"]
    for category, answer in zip(CATEGORIES, parts):
        normalized = _normalize(answer)
        duplicate = normalized in seen_answers
        seen_answers.add(normalized)
        valid = not duplicate and _validate_answer(category, letter, answer)
        score = 10 if valid else 0
        valid_parts += int(valid)
        if logger is not None:
            logger.log_info(
                "NAME FAMILY VALIDATION "
                f"chat_id={chat_id} user_id={user_id} "
                f"category={category} raw_answer={answer} "
                f"normalized_answer={normalized} letter={letter} "
                f"valid={valid} score={score}"
            )
    points = valid_parts * 10
    state["answers"][user_key] = {
        "user_id": user_key,
        "name": name,
        "points": points,
        "round_id": state["round_id"],
    }
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id):
    state = _ACTIVE.pop(chat_id, None)
    if not state:
        return []
    return sorted(
        state["answers"].values(),
        key=lambda item: item["points"],
        reverse=True,
    )
