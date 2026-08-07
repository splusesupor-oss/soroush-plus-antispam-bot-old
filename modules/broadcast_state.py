"""Single-session temporary broadcast state for the global bot owner.

The stored payload keeps the raw text *and* its MessageEntity list, because a
Soroush Plus announcement is only faithful if bold, blockquote and every other
entity survive the preview/confirm round trip. Storing text alone silently
downgrades a formatted announcement to plain text.
"""
import json
import os
import uuid as _uuid
from pathlib import Path


_STATE_FILE = Path(__file__).resolve().parent.parent / "config" / "broadcast_state.json"


def _load_pending():
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            # Recover from partial/corrupt entries without breaking the
            # private command handler for every future message.
            valid = {}
            for owner, state in data.items():
                if not isinstance(state, dict):
                    continue
                phase = state.get("phase")
                if phase not in {"awaiting_message", "awaiting_confirmation"}:
                    continue
                valid[str(owner)] = {
                    "phase": phase,
                    "text": state.get("text", ""),
                    "entities": [],
                }
            return valid
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _save_pending():
    """Persist only the pending workflow; delivery locks remain runtime-only."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = _STATE_FILE.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    owner: {
                        "phase": state.get("phase"),
                        "text": state.get("text", ""),
                        # Entities are process-local API objects; text and phase
                        # are the durable recovery contract.
                        "entities": [],
                    }
                    for owner, state in _PENDING_BROADCASTS.items()
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, _STATE_FILE)
    except OSError:
        # The caller keeps the in-memory state; the next operation retries the
        # write and the error is not allowed to crash message handling.
        pass


_PENDING_BROADCASTS = _load_pending()


# «اطلاع‌رسانی» با نیم‌فاصله (ZWNJ) همان دستور «اطلاع رسانی» است. کاربر معمولاً
# املای نیم‌فاصله را می‌نویسد — همان که خود ربات در پیام‌هایش نشان می‌دهد — و
# مقایسهٔ خام آن را رد می‌کرد. حروف عربی ی/ک هم به فارسی نگاشت می‌شوند.
_COMMAND_NORMALIZE_MAP = {
    "\u200c": " ",  # ZWNJ  -> space
    "\u200b": "",   # zero-width space
    "\u200f": "",   # RTL mark
    "\u200e": "",   # LTR mark
    "\ufeff": "",   # BOM
    "\u064a": "\u06cc",  # Arabic yeh -> Persian yeh
    "\u0649": "\u06cc",  # alef maksura -> Persian yeh
    "\u0643": "\u06a9",  # Arabic kaf  -> Persian kaf
}

# هر املایی که باید دستور اطلاع‌رسانی محسوب شود، پس از نرمال‌سازی.
BROADCAST_COMMAND_WORDS = frozenset({
    "اطلاع رسانی",
    "اطلاعرسانی",
    "تایید",
    "✅ تایید",
    "تأیید",
    "لغو",
    "❌ لغو",
})


def normalize_command_text(text):
    """متن را برای مقایسهٔ دستور یکسان‌سازی می‌کند (نیم‌فاصله، فاصلهٔ تکراری، حروف عربی)."""
    if not text:
        return ""
    normalized = str(text)
    for source, target in _COMMAND_NORMALIZE_MAP.items():
        normalized = normalized.replace(source, target)
    return " ".join(normalized.split())


def is_broadcast_command(text):
    """True اگر متن یکی از triggerهای اطلاع‌رسانی باشد.

    علاوه بر مقایسهٔ معمول، مقایسهٔ فشرده هم انجام می‌شود تا تفاوت‌های
    فاصله/نیم‌فاصله/کاراکترهای نامرئی بین کلاینت‌ها trigger را از بین نبرد.
    """
    normalized = normalize_command_text(text).strip("\"'«»،,:：؛.!؟")
    if normalized in BROADCAST_COMMAND_WORDS:
        return True
    compact = "".join(normalized.split())
    return compact in {"اطلاعرسانی", "تایید", "لغو"}


def clear(owner_id):
    """Destroy every pending value for this owner and persist the change."""
    _PENDING_BROADCASTS.pop(str(owner_id), None)
    _save_pending()


def begin(owner_id):
    """Start a brand-new persistent session, replacing any stale one."""
    clear(owner_id)
    _PENDING_BROADCASTS[str(owner_id)] = {"phase": "awaiting_message"}
    _save_pending()


def get(owner_id):
    return _PENDING_BROADCASTS.get(str(owner_id))


def set_message(owner_id, text, entities=None):
    """Store the announcement body together with its formatting entities."""
    # Keep entities in RAM for the current workflow; _save_pending strips
    # non-JSON API objects while persisting the durable text/phase.
    _PENDING_BROADCASTS[str(owner_id)] = {
        "phase": "awaiting_confirmation",
        "text": text,
        "entities": list(entities) if entities else [],
    }
    _save_pending()


def consume_confirmation(owner_id):
    """Atomically consume the only valid confirmation and destroy its state.

    Returns ``(text, entities)`` or ``(None, [])`` when there is nothing to
    confirm.
    """
    state = _PENDING_BROADCASTS.get(str(owner_id))
    if not state or state.get("phase") != "awaiting_confirmation":
        return None, []
    text = state.get("text")
    entities = list(state.get("entities") or [])
    clear(owner_id)
    return text, entities


# ---------------------------------------------------------------------------
# Delivery ledger
#
# ``_broadcast_to_groups`` keeps a *local* "seen" set, which cannot stop a
# second, concurrent invocation from delivering to the same groups. A dropped
# connection mid-broadcast, a replayed update after reconnect, or any future
# caller can start a second run while the first is still awaiting.
#
# The ledger below lives at module scope, so every invocation shares it. A
# group is claimed *before* the network call, and the claim is keyed by the
# normalized group id so the short and -100… forms are the same group.
# ---------------------------------------------------------------------------

_DELIVERY_LEDGER = {}
_LEDGER_ORDER = []
_LEDGER_LIMIT = 20
_BROADCAST_IN_FLIGHT = set()


def new_broadcast_id():
    """شناسهٔ تازه برای هر عملیات اطلاع‌رسانی.

    عمداً یکتا است: ledger فقط باید تحویل تکراری *در همان اجرا* را ببندد.
    اگر کلید از روی محتوا ساخته شود، ارسال دوبارهٔ عمدیِ همان اطلاعیه هم
    مسدود می‌شود و کاربر «۰ گروه» می‌گیرد — که یک باگ است، نه محافظت.
    """
    return _uuid.uuid4().hex[:12]


def start_delivery(broadcast_id):
    """Register a new broadcast and return its (empty) delivered-group set."""
    key = str(broadcast_id)
    if key not in _DELIVERY_LEDGER:
        _DELIVERY_LEDGER[key] = set()
        _LEDGER_ORDER.append(key)
        while len(_LEDGER_ORDER) > _LEDGER_LIMIT:
            _DELIVERY_LEDGER.pop(_LEDGER_ORDER.pop(0), None)
    return _DELIVERY_LEDGER[key]


def claim_group(broadcast_id, group_key):
    """Claim a group for this broadcast.

    Returns True only for the first caller; every later caller gets False.
    Synchronous on purpose: no ``await`` between the check and the insert, so
    concurrent tasks cannot both win the claim.
    """
    delivered = start_delivery(broadcast_id)
    key = str(group_key)
    if key in delivered:
        return False
    delivered.add(key)
    return True


def delivered_count(broadcast_id):
    return len(_DELIVERY_LEDGER.get(str(broadcast_id), ()))


def acquire_broadcast_slot(owner_id):
    """Global one-at-a-time guard. False when a broadcast is already running."""
    key = str(owner_id)
    if key in _BROADCAST_IN_FLIGHT:
        return False
    _BROADCAST_IN_FLIGHT.add(key)
    return True


def release_broadcast_slot(owner_id):
    _BROADCAST_IN_FLIGHT.discard(str(owner_id))


def is_broadcast_in_flight(owner_id):
    return str(owner_id) in _BROADCAST_IN_FLIGHT


def reset_delivery_state():
    """Test helper: forget every ledger entry and in-flight slot."""
    _DELIVERY_LEDGER.clear()
    _LEDGER_ORDER.clear()
    _BROADCAST_IN_FLIGHT.clear()
