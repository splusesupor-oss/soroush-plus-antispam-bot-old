"""Native admin RPC miss must be cached. No network."""
import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "splusthon" not in sys.modules:
    fake = types.ModuleType("splusthon")
    fake.Button = object
    fake.types = types.ModuleType("splusthon.types")
    tl = types.ModuleType("splusthon.tl")
    tl_types = types.ModuleType("splusthon.tl.types")

    class _Ent:
        def __init__(self, offset=0, length=0, **_kwargs):
            self.offset = offset
            self.length = length

    tl_types.MessageEntityBold = _Ent
    tl_types.MessageEntityBlockquote = _Ent
    tl.types = tl_types
    tl.functions = types.ModuleType("splusthon.tl.functions")
    fake.tl = tl
    sys.modules["splusthon"] = fake
    sys.modules["splusthon.tl"] = tl
    sys.modules["splusthon.tl.types"] = tl_types
    sys.modules["splusthon.tl.functions"] = tl.functions
    sys.modules["splusthon.types"] = fake.types

import handlers.message_handler as handler

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class _Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(message)

    def log_error(self, message):
        self.errors.append(message)


class _Config:
    def __init__(self, debug=False):
        self.debug = debug

    def get(self, key, default=None):
        if key == "debug_message_pipeline":
            return self.debug
        return default


class _Client:
    def __init__(self, error=None, is_admin=False):
        self.error = error
        self.is_admin = is_admin
        self.calls = []

    async def get_permissions(self, chat_id, user):
        self.calls.append((chat_id, user))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(is_admin=self.is_admin)


def _bot(client, debug=False):
    return SimpleNamespace(
        client=client,
        logger=_Logger(),
        config_manager=_Config(debug=debug),
        native_group_admin_cache={},
    )


def test_negative_native_admin_ttl_is_raised():
    print("\n### TTL نتیجه منفی native admin بالاتر از قبل است")
    check("fail TTL is 180s", handler._NATIVE_ADMIN_FAIL_TTL == 180,
          f"-> {handler._NATIVE_ADMIN_FAIL_TTL}")
    check("non-admin TTL is 90s", handler._NATIVE_ADMIN_NEGATIVE_TTL == 90,
          f"-> {handler._NATIVE_ADMIN_NEGATIVE_TTL}")


def test_keyerror_is_fail_closed_and_cached():
    print("\n### KeyError سروش → False و بدون RPC دوباره")
    client = _Client(error=KeyError(12345))
    bot = _bot(client)

    async def run():
        first = await handler._is_native_group_admin(bot, -1001, 77, None)
        second = await handler._is_native_group_admin(bot, -1001, 77, None)
        return first, second

    first, second = asyncio.run(run())
    check("first call fail-closed", first is False, f"-> {first}")
    check("second call still False", second is False, f"-> {second}")
    check("get_permissions called once", len(client.calls) == 1, f"-> {client.calls}")
    check("one error log", len(bot.logger.errors) == 1, f"-> {bot.logger.errors}")
    check(
        "error mentions KeyError",
        any("KeyError" in item for item in bot.logger.errors),
        f"-> {bot.logger.errors}",
    )


def test_repeat_keyerror_does_not_relog():
    print("\n### تکرار KeyError در TTL لاگ تازه نمی‌نویسد")
    client = _Client(error=KeyError("missing user"))
    bot = _bot(client)

    async def run():
        await handler._is_native_group_admin(bot, -1002, 88, "sender")
        client.error = KeyError("again")
        await handler._is_native_group_admin(bot, -1002, 88, "sender")
        await handler._is_native_group_admin(bot, -1002, 88, "sender")

    asyncio.run(run())
    check("still one RPC", len(client.calls) == 1, f"-> {len(client.calls)}")
    check("still one error log", len(bot.logger.errors) == 1, f"-> {len(bot.logger.errors)}")


def test_successful_admin_is_cached():
    print("\n### ادمین واقعی کش می‌شود")
    client = _Client(is_admin=True)
    bot = _bot(client)

    async def run():
        first = await handler._is_native_group_admin(bot, -1003, 99, None)
        second = await handler._is_native_group_admin(bot, -1003, 99, None)
        return first, second

    first, second = asyncio.run(run())
    check("first True", first is True)
    check("second True", second is True)
    check("one RPC", len(client.calls) == 1, f"-> {client.calls}")
    check("no error log", bot.logger.errors == [], f"-> {bot.logger.errors}")


def test_successful_member_is_cached():
    print("\n### عضو عادی هم کش می‌شود")
    client = _Client(is_admin=False)
    bot = _bot(client)

    async def run():
        first = await handler._is_native_group_admin(bot, -1004, 11, None)
        second = await handler._is_native_group_admin(bot, -1004, 11, None)
        return first, second

    first, second = asyncio.run(run())
    check("first False", first is False)
    check("second False", second is False)
    check("one RPC", len(client.calls) == 1, f"-> {client.calls}")


def test_expired_failure_retries():
    print("\n### بعد از TTL شکست، RPC دوباره زده می‌شود")
    client = _Client(error=KeyError("gone"))
    bot = _bot(client)

    async def run():
        first = await handler._is_native_group_admin(bot, -1005, 22, None)
        key = next(iter(bot.native_group_admin_cache))
        value, expires = bot.native_group_admin_cache[key]
        bot.native_group_admin_cache[key] = (value, expires - 1000)
        client.error = None
        client.is_admin = True
        second = await handler._is_native_group_admin(bot, -1005, 22, None)
        return first, second

    first, second = asyncio.run(run())
    check("expired miss was False", first is False)
    check("retry saw admin", second is True)
    check("two RPCs after expiry", len(client.calls) == 2, f"-> {len(client.calls)}")


def test_ban_execution_and_admin_check_logs_are_debug_only():
    print("\n### لاگ BAN/ADMIN CHECK فقط در debug")
    quiet = SimpleNamespace(
        logger=_Logger(),
        config_manager=_Config(debug=False),
        punished_users=set(),
    )
    noisy = SimpleNamespace(
        logger=_Logger(),
        config_manager=_Config(debug=True),
        punished_users=set(),
    )
    handler._log_ban_execution(quiet, -1, 2, "اسپم")
    handler._log_ban_execution(noisy, -1, 2, "اسپم")
    check("quiet ban log off", quiet.logger.infos == [])
    check("debug ban log on", any("BAN EXECUTION DEBUG" in item for item in noisy.logger.infos))

    orig_owner = handler.is_global_owner
    orig_admin = handler.is_admin
    orig_group_owner = handler.get_group_owner
    handler.ADMIN_PERMISSION_CACHE.clear()

    async def run_checks():
        handler.is_global_owner = lambda _uid: True
        handler.is_admin = lambda *_a, **_k: False
        handler.get_group_owner = lambda _chat: None
        handler._has_group_management_permission(quiet, -9, 5, "x")
        handler.ADMIN_PERMISSION_CACHE.clear()
        handler._has_group_management_permission(noisy, -8, 6, "y")

    try:
        asyncio.run(run_checks())
    finally:
        handler.is_global_owner = orig_owner
        handler.is_admin = orig_admin
        handler.get_group_owner = orig_group_owner
        handler.ADMIN_PERMISSION_CACHE.clear()
    check("quiet admin check off", quiet.logger.infos == [])
    check(
        "debug admin check on",
        any("ADMIN CHECK DEBUG" in item for item in noisy.logger.infos),
        f"-> {noisy.logger.infos}",
    )


if __name__ == "__main__":
    test_negative_native_admin_ttl_is_raised()
    test_keyerror_is_fail_closed_and_cached()
    test_repeat_keyerror_does_not_relog()
    test_successful_admin_is_cached()
    test_successful_member_is_cached()
    test_expired_failure_retries()
    test_ban_execution_and_admin_check_logs_are_debug_only()
    print(f"\n{PASSED} passed, {FAILED} failed")
    raise SystemExit(1 if FAILED else 0)
