"""بازی مستقل «حدس جمله» با بانک و state جداگانه."""
import json
import random
import time
from pathlib import Path
from .sentence_guess_puzzles import PUZZLES

COMMAND = "حدس جمله"
TIMEOUT_SECONDS = 30
REWARD = 4
FILE = Path(__file__).resolve().parents[2] / "config" / "sentence_guess_state.json"
_ACTIVE = {}


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(chat_id):
    return str(chat_id)


def _recover(chat_id):
    key = _key(chat_id)
    state = _ACTIVE.get(key)
    if state:
        return state
    state = _load().get(key)
    if not isinstance(state, dict):
        return None
    if time.time() - float(state.get("started_at", 0)) >= TIMEOUT_SECONDS:
        _clear(chat_id)
        return None
    _ACTIVE[key] = state
    return state


def _clear(chat_id):
    key = _key(chat_id)
    _ACTIVE.pop(key, None)
    data = _load()
    if key in data:
        data.pop(key, None)
        _save(data)


def is_active(chat_id):
    return _recover(chat_id) is not None


def start(chat_id):
    if _recover(chat_id) is not None:
        return None
    index = random.randrange(len(PUZZLES))
    question, answer = PUZZLES[index]
    state = {"index": index, "question": question, "answer": answer,
             "started_at": time.time()}
    _ACTIVE[_key(chat_id)] = state
    data = _load(); data[_key(chat_id)] = state; _save(data)
    return dict(state)


def current(chat_id):
    state = _recover(chat_id)
    return dict(state) if state else None


def _norm(value):
    return " ".join(str(value or "").lower().replace("‌", " ").split())


def answer(chat_id, text):
    state = _recover(chat_id)
    if state is None:
        return None
    if _norm(text) != _norm(state["answer"]):
        return None
    result = dict(state)
    _clear(chat_id)
    return result


def timeout(chat_id):
    state = _recover(chat_id)
    if state is None:
        return None
    result = dict(state)
    _clear(chat_id)
    return result


def reset_all(chat_id=None):
    if chat_id is None:
        _ACTIVE.clear()
        if FILE.exists(): FILE.unlink()
    else:
        _clear(chat_id)
