"""Offline proof that a broadcast reaches each group exactly once.

Reproduces the real duplicate-send bug: ``iter_dialogs()`` reports the full
``-100…`` id while ``config/groups.json`` stores the short id, so a raw-string
"seen" set treated one group as two.

    python tests/test_broadcast_dedup.py
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from splusthon.tl.types import MessageEntityBold

import handlers.broadcast_handler as bh
import modules.broadcast_state as bstate
from modules.group_id import CHANNEL_ID_OFFSET, normalize_group_id

OWNER_ID = 68074059
SHORT_IDS = ["23164149", "23093376", "22770700"]
FULL_IDS = [-(CHANNEL_ID_OFFSET + int(s)) for s in SHORT_IDS]

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class Logger:
    def __init__(self):
        self.lines = []

    def log_info(self, m):
        self.lines.append(m)

    def log_error(self, m):
        self.lines.append("ERROR " + m)

    def has(self, n):
        return any(n in m for m in self.lines)

    def count(self, n):
        return sum(1 for m in self.lines if n in m)


class Dialog:
    def __init__(self, cid):
        self.id = cid
        self.is_group = True
        self.entity = f"entity:{cid}"


class Client:
    """iter_dialogs yields FULL ids; config holds SHORT ids."""

    def __init__(self, dialog_ids=None, fail_enumeration=False):
        self.sent = []
        self.dialog_ids = dialog_ids if dialog_ids is not None else list(FULL_IDS)
        self.fail_enumeration = fail_enumeration

    async def send_message(self, entity, message, formatting_entities=None, **kw):
        self.sent.append(entity)
        return None

    def iter_dialogs(self):
        outer = self

        async def gen():
            if outer.fail_enumeration:
                raise RuntimeError("cannot enumerate dialogs")
            for cid in outer.dialog_ids:
                yield Dialog(cid)
        return gen()


class Msg:
    def __init__(self, text, entities=None):
        self.message = text
        self.entities = list(entities or [])
        self.id = 1


class Event:
    def __init__(self, text, entities=None):
        self.message = Msg(text, entities)
        self.replies = []

    async def reply(self, text, formatting_entities=None, **kw):
        self.replies.append(text)
        return None


class Bot:
    def __init__(self, client):
        self.logger = Logger()
        self.client = client


def target_key(t):
    """Normalise whatever was passed to send_message into a group key."""
    s = str(t).replace("entity:", "")
    return normalize_group_id(s)


def run_broadcast(client, body="اطلاعیه", entities=None):
    bstate.clear(OWNER_ID)
    bot = Bot(client)
    asyncio.run(bh.handle_private_broadcast(
        bot, Event("اطلاع رسانی"), OWNER_ID, "اطلاع رسانی"))
    asyncio.run(bh.handle_private_broadcast(
        bot, Event(body, entities), OWNER_ID, body))
    ev = Event("تایید")
    asyncio.run(bh.handle_private_broadcast(bot, ev, OWNER_ID, "تایید"))
    bstate.clear(OWNER_ID)
    return bot, ev


def test_no_duplicates_both_routes():
    print("\n### dialogs (-100…) + config (short) must not double-send")
    client = Client()
    bot, ev = run_broadcast(client)
    keys = [target_key(t) for t in client.sent]
    counts = Counter(keys)
    dupes = {k: c for k, c in counts.items() if c > 1}
    check("each group received exactly one message", not dupes, f"-> {dupes}")
    check(f"total sends == {len(SHORT_IDS)} unique groups",
          len(client.sent) == len(SHORT_IDS), f"-> {len(client.sent)}")
    check("all expected groups covered",
          set(counts) == {normalize_group_id(s) for s in SHORT_IDS},
          f"-> {set(counts)}")
    check("skip was logged for the config duplicates",
          bot.logger.count("BROADCAST GROUP SKIPPED") >= 1
          or bot.logger.count("BROADCAST GROUP SENT") == len(SHORT_IDS))
    check("summary reports the real count",
          bot.logger.has(f"successful={len(SHORT_IDS)}"),
          f"-> {[m for m in bot.logger.lines if 'SEND RESULT' in m]}")
    check("owner told the correct number",
          any(f"گروه‌های موفق: {len(SHORT_IDS)}" in r for r in ev.replies),
          f"-> {ev.replies}")


def test_dialog_repeats_same_group():
    print("\n### the same dialog yielded twice is sent once")
    client = Client(dialog_ids=FULL_IDS + FULL_IDS)
    bot, _ = run_broadcast(client)
    counts = Counter(target_key(t) for t in client.sent)
    check("no group received twice",
          all(c == 1 for c in counts.values()), f"-> {dict(counts)}")
    check(f"exactly {len(SHORT_IDS)} sends", len(client.sent) == len(SHORT_IDS),
          f"-> {len(client.sent)}")


def test_mixed_short_and_full_dialog_ids():
    print("\n### dialogs reporting short ids too")
    client = Client(dialog_ids=FULL_IDS + [int(s) for s in SHORT_IDS])
    bot, _ = run_broadcast(client)
    counts = Counter(target_key(t) for t in client.sent)
    check("short and full ids treated as one group",
          all(c == 1 for c in counts.values()), f"-> {dict(counts)}")
    check(f"exactly {len(SHORT_IDS)} sends", len(client.sent) == len(SHORT_IDS),
          f"-> {len(client.sent)}")


def test_enumeration_failure_still_delivers_once():
    print("\n### dialog enumeration fails -> config fallback, still once")
    client = Client(fail_enumeration=True)
    bot, _ = run_broadcast(client)
    counts = Counter(target_key(t) for t in client.sent)
    check("fallback delivered to every group",
          set(counts) == {normalize_group_id(s) for s in SHORT_IDS},
          f"-> {set(counts)}")
    check("no duplicates via fallback",
          all(c == 1 for c in counts.values()), f"-> {dict(counts)}")
    check("enumeration failure logged",
          bot.logger.has("DIALOG ENUMERATION FAILED"))


def test_double_confirm_sends_once():
    print("\n### pressing تایید twice sends only one broadcast")
    client = Client()
    bstate.clear(OWNER_ID)
    bot = Bot(client)
    asyncio.run(bh.handle_private_broadcast(
        bot, Event("اطلاع رسانی"), OWNER_ID, "اطلاع رسانی"))
    asyncio.run(bh.handle_private_broadcast(
        bot, Event("متن"), OWNER_ID, "متن"))
    asyncio.run(bh.handle_private_broadcast(bot, Event("تایید"), OWNER_ID, "تایید"))
    first = len(client.sent)
    asyncio.run(bh.handle_private_broadcast(bot, Event("تایید"), OWNER_ID, "تایید"))
    second = len(client.sent)
    check(f"first confirm sent {len(SHORT_IDS)}", first == len(SHORT_IDS), f"-> {first}")
    check("second confirm sent nothing", second == first, f"-> {second}")
    check("state destroyed", bstate.get(OWNER_ID) is None)
    bstate.clear(OWNER_ID)


def test_unique_broadcast_id():
    print("\n### each broadcast carries its own id")
    ids = []
    for _ in range(2):
        client = Client()
        bot, _ = run_broadcast(client)
        line = next((m for m in bot.logger.lines if "BROADCAST SEND START" in m), "")
        bid = line.split("broadcast_id=")[1].split()[0] if "broadcast_id=" in line else None
        ids.append(bid)
    check("broadcast_id present", all(ids), f"-> {ids}")
    check("ids differ between runs", ids[0] != ids[1], f"-> {ids}")


def test_entities_survive_dedup():
    print("\n### formatting still delivered once, intact")
    client = Client()
    ents = [MessageEntityBold(offset=0, length=7)]
    bot, _ = run_broadcast(client, body="اطلاعیه مهم", entities=ents)
    check(f"one message per group", len(client.sent) == len(SHORT_IDS),
          f"-> {len(client.sent)}")
    check("entity count logged", bot.logger.has("entity_count=1"))


def main():
    bh.is_active = lambda gid: normalize_group_id(gid) in {
        normalize_group_id(s) for s in SHORT_IDS
    }
    bh.load_groups = lambda: {s: {"active": True} for s in SHORT_IDS}

    test_no_duplicates_both_routes()
    test_dialog_repeats_same_group()
    test_mixed_short_and_full_dialog_ids()
    test_enumeration_failure_still_delivers_once()
    test_double_confirm_sends_once()
    test_unique_broadcast_id()
    test_entities_survive_dedup()

    print(f"\n{'=' * 52}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
