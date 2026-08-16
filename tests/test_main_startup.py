"""Startup path used by main.py must not raise on MessagePacker slots."""
import asyncio
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.outgoing_profiler import instrument_client
from modules.outgoing_rpc import _PrioritySendQueue, install

PASSED = FAILED = 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name} {detail}")


class Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(message)

    def log_error(self, message):
        self.errors.append(message)


class SlottedMessagePacker:
    __slots__ = ("_state", "_deque", "_ready", "_log", "_buffer")

    def __init__(self):
        from collections import deque
        self._state = None
        self._deque = deque()
        self._ready = asyncio.Event()
        self._log = None
        self._buffer = None

    def append(self, state):
        self._deque.append(state)
        self._ready.set()

    def extend(self, states):
        self._deque.extend(states)
        self._ready.set()


class StartupSender:
    def __init__(self):
        self._pending_state = {}
        self._send_queue = SlottedMessagePacker()

    async def _reconnect(self, last_error):
        return "ok"


class StartupClient:
    """Same lifecycle as SoroushClient: packer appears only after connect."""

    def __init__(self):
        self._sender = None

    async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
        return "ok"

    async def send_message(self, *a, **k):
        return "sent"

    async def delete_messages(self, *a, **k):
        return "deleted"

    async def edit_permissions(self, *a, **k):
        return "muted"

    async def kick_participant(self, *a, **k):
        return "banned"

    async def connect(self, *a, **k):
        self._sender = StartupSender()
        return True


def test_main_py_parses():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    check("main.py سینتکس معتبر دارد", tree is not None)
    check("main.py از SoroushAntiSpamBot استفاده می‌کند",
          "SoroushAntiSpamBot" in source)


def test_initialize_then_connect_like_main():
    print("\n### startup: instrument + install + connect مثل main.py")

    async def scenario():
        logger = Logger()
        client = StartupClient()
        instrument_client(client, logger)
        install(client, logger)
        await client.connect()
        return client

    client = asyncio.run(scenario())
    queue = client._sender._send_queue
    check("connect بدون AttributeError تمام شد", client._sender is not None)
    check("MessagePacker با proxy پوشانده شد",
          isinstance(queue, _PrioritySendQueue), f"-> {type(queue)}")
    check("خود MessagePacker دست نخورده است",
          isinstance(queue._inner, SlottedMessagePacker))


def main():
    test_main_py_parses()
    test_initialize_then_connect_like_main()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
