"""Offline proof of the independent PV /start + test-button path."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from handlers import private_handler as pv


PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class FakeMessage:
    def __init__(self, text=""):
        self.message = text
        self.caption = None
        self.id = 11


class FakeEvent:
    def __init__(self, text="", is_private=True, chat_id=68074059, data=None):
        self.message = FakeMessage(text)
        self.is_private = is_private
        self.chat_id = chat_id
        self.data = data
        self.replies = []
        self.answers = []
        self.edits = []
        self.sends = []

    async def reply(self, text, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(id=99, text=text)

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return True

    async def edit(self, text, **kwargs):
        self.edits.append((text, kwargs))
        return SimpleNamespace(id=11, text=text)


class FakeLogger:
    def __init__(self):
        self.lines = []

    def log_info(self, message):
        self.lines.append(("INFO", message))

    def log_error(self, message):
        self.lines.append(("ERROR", message))


class FakeBot:
    def __init__(self):
        self.logger = FakeLogger()
        self.client = SimpleNamespace(send_message=self._send)

    async def _send(self, chat_id, text, **kwargs):
        return SimpleNamespace(id=100, chat_id=chat_id, text=text)


def test_start_matching():
    print("\n### /start matching")
    check("/start", pv.is_start_command("/start"))
    check("/START", pv.is_start_command("/START"))
    check("/start@foxbot", pv.is_start_command("/start@foxbot"))
    check("  /start  ", pv.is_start_command("  /start  "))
    check("start without slash is ignored", not pv.is_start_command("start"))
    check("group command ignored", not pv.is_start_command("راهنما"))
    check("empty ignored", not pv.is_start_command(""))
    check("None ignored", not pv.is_start_command(None))
    check("/started is not /start", not pv.is_start_command("/started"))


def test_private_detection():
    print("\n### private detection")
    check("is_private True", pv.is_private_event(FakeEvent(is_private=True)))
    check("is_private False on group id",
          not pv.is_private_event(FakeEvent(is_private=False, chat_id=-1000023164149)))
    check("None is not private", not pv.is_private_event(None))
    group = FakeEvent(is_private=False, chat_id=-1000023164149)
    check("group event is not private", not pv.is_private_event(group))
    splus_dm = FakeEvent("/start", is_private=False, chat_id=68074059)
    check("SPlusthon DM positive chat_id is private", pv.is_private_event(splus_dm))
    class Chat:
        pass
    named_dm = FakeEvent("/start", is_private=False, chat_id=68074059)
    named_dm.chat = Chat()
    check("positive chat_id wins over Chat class name", pv.is_private_event(named_dm))
    named_group = FakeEvent("/start", is_private=False, chat_id=-1000023164149)
    named_group.chat = Chat()
    check("negative chat_id stays group even with Chat class", not pv.is_private_event(named_group))
    class PeerUser:
        pass

    peer_event = FakeEvent(is_private=False)
    peer_event._chat_peer = PeerUser()
    check("PeerUser fallback is private", pv.is_private_event(peer_event))


def test_keyboard_layout():
    print("\n### keyboard layout")
    keyboard = pv.start_keyboard()
    if keyboard is None:
        check("keyboard unavailable without splusthon Button", True)
        return
    check("one row", len(keyboard) == 1, f"rows={keyboard!r}")
    check("one button on that row", len(keyboard[0]) == 1)
    button = keyboard[0][0]
    text = getattr(button, "text", None) or getattr(button, "label", None)
    data = getattr(button, "data", None)
    check("button text", text == pv.TEST_BUTTON_TEXT, f"text={text!r}")
    check("callback_data", data == pv.TEST_BUTTON_DATA, f"data={data!r}")


def test_private_start_sends_button():
    print("\n### PV /start reply")
    bot = FakeBot()
    event = FakeEvent("/start", is_private=True)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("consumed", handled is True)
    check("one reply", len(event.replies) == 1, f"replies={event.replies!r}")
    text, kwargs = event.replies[0]
    check("welcome text", text == pv.START_TEXT, f"text={text!r}")
    buttons = kwargs.get("buttons")
    if buttons is None:
        check("buttons omitted only if Button import missing", pv.start_keyboard() is None)
    else:
        check("full-width single row", len(buttons) == 1 and len(buttons[0]) == 1)
    check("no extra answer", event.answers == [])
    check("no extra edit", event.edits == [])


def test_group_start_not_consumed():
    print("\n### group /start is ignored")
    bot = FakeBot()
    event = FakeEvent("/start", is_private=False, chat_id=-1000023164149)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("not consumed", handled is False)
    check("no group reply", event.replies == [])


def test_other_private_text_not_consumed():
    print("\n### other PV text stays on the existing path")
    bot = FakeBot()
    event = FakeEvent("لیست انقضا", is_private=True)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("not consumed", handled is False)
    check("no reply", event.replies == [])


def test_callback_answers_without_new_message():
    print("\n### callback answer, no extra message")
    bot = FakeBot()
    event = FakeEvent(is_private=True, data=b"test_button")
    handled = asyncio.run(pv.handle_private_callback(bot, event))
    check("consumed", handled is True)
    check("answered toast", event.answers == [(pv.TEST_OK_TEXT, {})], f"answers={event.answers!r}")
    check("visible PV reply", event.replies == [(pv.TEST_OK_TEXT, {})], f"replies={event.replies!r}")
    check("no fallback edit when reply works", event.edits == [])
    logs = "\n".join(line for _level, line in bot.logger.lines)
    check("button received log", "PV TEST BUTTON RECEIVED" in logs)
    check("button sent log", "PV TEST BUTTON RESPONSE SENT" in logs)


def test_callback_edit_fallback():
    print("\n### callback edit fallback")

    class NoAnswerEvent(FakeEvent):
        async def answer(self, text, **kwargs):
            raise RuntimeError("toast unavailable")

        async def reply(self, text, **kwargs):
            raise RuntimeError("reply unavailable")

    bot = FakeBot()
    event = NoAnswerEvent(is_private=True, data=b"test_button")
    handled = asyncio.run(pv.handle_private_callback(bot, event))
    check("consumed via edit", handled is True)
    check("no extra reply when reply missing", event.replies == [])
    check("edited same message", event.edits and event.edits[0][0] == pv.TEST_OK_TEXT,
          f"edits={event.edits!r}")


def test_callback_ignores_other_data_and_groups():
    print("\n### callback isolation")
    bot = FakeBot()
    other = FakeEvent(is_private=True, data=b"test_salam")
    check("other callback ignored",
          asyncio.run(pv.handle_private_callback(bot, other)) is False)
    check("other callback no reply", other.replies == [])
    group = FakeEvent(is_private=False, chat_id=-1001, data=b"test_button")
    check("group callback ignored",
          asyncio.run(pv.handle_private_callback(bot, group)) is False)
    check("group callback no reply", group.replies == [])


def test_unresolved_pv_start_without_chat_id():
    print("\n### PV /start with is_private=False and chat_id=None")
    bot = FakeBot()
    event = FakeEvent("/start", is_private=False, chat_id=None)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("consumed unresolved PV /start", handled is True)
    check("welcome sent", event.replies and event.replies[0][0] == pv.START_TEXT)
    logs = "\n".join(line for _level, line in bot.logger.lines)
    check("PV START RECEIVED", "PV START RECEIVED" in logs)
    check("PV START SENT", "PV START SENT" in logs)


def test_splus_private_start_when_is_private_false():
    print("\n### SPlusthon PV /start with is_private=False")
    bot = FakeBot()
    event = FakeEvent("/start", is_private=False, chat_id=68074059)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("consumed", handled is True)
    check("welcome sent", event.replies and event.replies[0][0] == pv.START_TEXT)
    logs = "\n".join(line for _level, line in bot.logger.lines)
    check("PV START RECEIVED", "PV START RECEIVED" in logs)
    check("PV START ROUTED", "PV START ROUTED" in logs)
    check("PV START HANDLER", "PV START HANDLER" in logs)
    check("PV START SENT", "PV START SENT" in logs)


def test_start_from_raw_text_field():
    print("\n### /start on raw_text when message.message is empty")
    bot = FakeBot()
    event = FakeEvent("", is_private=True, chat_id=42)
    event.message.message = ""
    event.raw_text = "/start"
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("consumed from raw_text", handled is True)
    check("welcome sent", event.replies and event.replies[0][0] == pv.START_TEXT)


def test_group_start_not_routed_to_pv_even_with_slash():
    print("\n### group /start stays out of PV handler")
    bot = FakeBot()
    event = FakeEvent("/start", is_private=False, chat_id=-1000023164149)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("not consumed", handled is False)
    check("no PV reply", event.replies == [])
    logs = "\n".join(line for _level, line in bot.logger.lines)
    check("received log still emitted", "PV START RECEIVED" in logs)
    check("not routed", "PV START ROUTED" not in logs)
    check("not sent", "PV START SENT" not in logs)


def test_normal_pv_text_stays_on_pv_path_without_start_reply():
    print("\n### normal PV text is private but not /start")
    bot = FakeBot()
    event = FakeEvent("سلام", is_private=False, chat_id=68074059)
    handled = asyncio.run(pv.try_handle_private_start(bot, event))
    check("detected private", pv.is_private_event(event) is True)
    check("not consumed as /start", handled is False)
    check("no start reply", event.replies == [])


def test_core_wiring():
    print("\n### core wiring stays a thin intercept")
    src = (ROOT / "core" / "bot_working_split_ok.py").read_text(encoding="utf-8")
    check("imports try_handle_private_start",
          "try_handle_private_start" in src)
    check("imports register_private_handlers",
          "register_private_handlers" in src)
    check("PV start intercepts NewMessage",
          "if await try_handle_private_start(self, event):" in src)
    check("callback registered independently",
          "register_private_handlers(self)" in src)
    check("group dispatcher still present",
          "self.group_dispatcher.submit(" in src)


def main():
    test_start_matching()
    test_private_detection()
    test_keyboard_layout()
    test_private_start_sends_button()
    test_group_start_not_consumed()
    test_other_private_text_not_consumed()
    test_callback_answers_without_new_message()
    test_callback_edit_fallback()
    test_callback_ignores_other_data_and_groups()
    test_unresolved_pv_start_without_chat_id()
    test_splus_private_start_when_is_private_false()
    test_start_from_raw_text_field()
    test_group_start_not_routed_to_pv_even_with_slash()
    test_normal_pv_text_stays_on_pv_path_without_start_reply()
    test_core_wiring()
    print(f"\n{'=' * 52}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
