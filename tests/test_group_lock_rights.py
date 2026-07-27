"""Offline proof that قفل/باز only ever touches default send_messages.

Runs with no network and no Soroush session: the client and logger are fakes.

    python tests/test_group_lock_rights.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from splusthon.tl import functions, types

import modules.group_actions as ga
from modules.group_actions import BANNED_RIGHT_FLAGS, GroupActions

CHAT_ID = -1000023164149
CHANNEL_ID = 23164149


class FakeLogger:
    def __init__(self):
        self.info = []
        self.error = []

    def log_info(self, message):
        self.info.append(message)

    def log_error(self, message):
        self.error.append(message)


class FakeClient:
    """Minimal stand-in that records the requests it is handed."""

    def __init__(self, server_rights):
        self.server_rights = server_rights
        self.sent = []

    async def get_input_entity(self, chat_id):
        if int(chat_id) != CHAT_ID:
            raise ValueError(f"unknown peer {chat_id}")
        return types.InputPeerChannel(channel_id=CHANNEL_ID, access_hash=12345)

    async def get_entity(self, chat_id):
        raise AssertionError(
            "get_entity() must not be the primary source (it can serve stale cache)"
        )

    async def __call__(self, request):
        self.sent.append(request)
        if isinstance(request, functions.channels.GetFullChannelRequest):
            chat = types.Channel(
                id=CHANNEL_ID,
                title="Test Group",
                photo=None,
                date=None,
                creator=False,
                left=False,
                broadcast=False,
                megagroup=True,
                default_banned_rights=self.server_rights,
            )
            return types.messages.ChatFull(
                full_chat=types.ChannelFull(
                    id=CHANNEL_ID,
                    about="",
                    read_inbox_max_id=0,
                    read_outbox_max_id=0,
                    unread_count=0,
                    chat_photo=None,
                    notify_settings=None,
                    bot_info=[],
                    pts=0,
                ),
                chats=[chat],
                users=[],
            )
        if isinstance(
            request, functions.messages.EditChatDefaultBannedRightsRequest
        ):
            self.server_rights = request.banned_rights
            return types.Updates(
                updates=[], users=[], chats=[], date=None, seq=0
            )
        raise AssertionError(f"unexpected request {type(request).__name__}")

    @property
    def edit_requests(self):
        return [
            r
            for r in self.sent
            if isinstance(r, functions.messages.EditChatDefaultBannedRightsRequest)
        ]


def flags_of(rights):
    if rights is None:
        return {flag: False for flag in BANNED_RIGHT_FLAGS}
    return {flag: bool(getattr(rights, flag, None)) for flag in BANNED_RIGHT_FLAGS}


PASSED = 0
FAILED = 0


def check(label, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


def assert_only_send_messages_changed(before, after, expected_send_messages):
    b, a = flags_of(before), flags_of(after)
    others = [f for f in BANNED_RIGHT_FLAGS if f != "send_messages" and b[f] != a[f]]
    check("no other permission changed", not others, f"-> changed: {others}")
    check(
        f"send_messages banned == {expected_send_messages}",
        a["send_messages"] is expected_send_messages,
        f"-> got {a['send_messages']}",
    )


def scenario(name, server_rights):
    print(f"\n### {name}")
    logger = FakeLogger()
    client = FakeClient(server_rights)
    actions = GroupActions(client, logger)
    before = flags_of(server_rights)

    asyncio.run(actions.lock_group(CHAT_ID))
    locked = client.server_rights
    check(
        "lock used EditChatDefaultBannedRightsRequest",
        len(client.edit_requests) == 1,
    )
    assert_only_send_messages_changed(server_rights, locked, True)

    asyncio.run(actions.unlock_group(CHAT_ID))
    unlocked = client.server_rights
    assert_only_send_messages_changed(locked, unlocked, False)

    after = flags_of(unlocked)
    restored = [
        f
        for f in BANNED_RIGHT_FLAGS
        if f != "send_messages" and before[f] != after[f]
    ]
    check("full lock->unlock cycle preserves all other flags", not restored,
          f"-> drifted: {restored}")

    names = [type(r).__name__ for r in client.sent]
    check(
        "ToggleJoinToSendRequest never used",
        not any("ToggleJoinToSend" in n for n in names),
    )
    check(
        "edit_permissions() helper never used",
        not any("EditBanned" in n for n in names),
    )


def test_no_rights_object():
    print("\n### group with default_banned_rights = None")
    logger = FakeLogger()
    client = FakeClient(None)
    actions = GroupActions(client, logger)
    asyncio.run(actions.lock_group(CHAT_ID))
    r = client.server_rights
    check("send_messages banned", bool(r.send_messages))
    others = [
        f for f in BANNED_RIGHT_FLAGS if f != "send_messages" and getattr(r, f)
    ]
    check("no other flag invented", not others, f"-> {others}")


def test_clone_helper():
    print("\n### clone_banned_rights unit checks")
    src = types.ChatBannedRights(
        until_date=None, send_gifs=True, send_polls=True, pin_messages=True
    )
    out = ga.clone_banned_rights(src, send_messages=True)
    check("send_gifs preserved", out.send_gifs is True)
    check("send_polls preserved", out.send_polls is True)
    check("pin_messages preserved", out.pin_messages is True)
    check("send_messages applied", out.send_messages is True)
    check("send_media untouched", out.send_media is False)
    check("source object not mutated", src.send_messages in (None, False))


def main():
    # Realistic group: media/gif/poll/invite/pin already restricted by the owner.
    test_clone_helper()
    scenario(
        "group with many pre-existing restrictions",
        types.ChatBannedRights(
            until_date=None,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_polls=True,
            embed_links=True,
            invite_users=True,
            pin_messages=True,
            change_info=True,
        ),
    )
    scenario(
        "group with zero restrictions",
        types.ChatBannedRights(until_date=None),
    )
    scenario(
        "group already locked before the command",
        types.ChatBannedRights(
            until_date=None, send_messages=True, send_media=True
        ),
    )
    test_no_rights_object()

    print(f"\n{'=' * 46}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 46)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
