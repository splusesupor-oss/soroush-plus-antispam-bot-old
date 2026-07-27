"""Administrative group actions for Soroush Plus.

Lock/unlock policy
------------------
"قفل" and "باز" must toggle *only* the default ``send_messages`` restriction
of the group. Every other default right (media, stickers, gifs, games, inline,
embed links, polls, change info, invite users, pin messages, topics, photos,
videos, round videos, audios, voices, docs, plain text) is read from the server
and written back untouched.

Deliberately NOT used here:

* ``ToggleJoinToSendRequest`` - it only switches the "must join to send" mode.
  Existing members keep writing, so the group never actually locks.
* ``client.edit_permissions()`` - its keyword arguments all default to ``True``
  ("not restricted"), so calling it with a single argument silently clears
  every other restriction the group had configured.

The single correct request is
``messages.EditChatDefaultBannedRightsRequest`` carrying a full
``ChatBannedRights`` object that we cloned from the current server state.

Note on ChatBannedRights semantics: a flag set to ``True`` means the right is
*banned*. So locking is ``send_messages=True`` and unlocking is
``send_messages=False``.
"""
import json
import traceback
from pathlib import Path

from splusthon.tl import functions, types
from splusthon.tl.functions.channels import EditPhotoRequest, EditTitleRequest

from modules.group_id import CHANNEL_ID_OFFSET, normalize_group_id


# Every ChatBannedRights flag, in the order declared by the schema. Used to
# clone the server state field-by-field so a library upgrade that adds a new
# flag cannot silently drop it.
BANNED_RIGHT_FLAGS = (
    "view_messages",
    "send_messages",
    "send_media",
    "send_stickers",
    "send_gifs",
    "send_games",
    "send_inline",
    "embed_links",
    "send_polls",
    "change_info",
    "invite_users",
    "pin_messages",
    "manage_topics",
    "send_photos",
    "send_videos",
    "send_roundvideos",
    "send_audios",
    "send_voices",
    "send_docs",
    "send_plain",
)

_LOCK_STATE_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "group_message_lock_state.json"
)


def _load_lock_state():
    try:
        if _LOCK_STATE_FILE.exists():
            return json.loads(_LOCK_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {}


def _save_lock_state(data):
    try:
        _LOCK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_STATE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        # Persisting the snapshot is best-effort telemetry; never block a lock.
        pass


def clone_banned_rights(rights, **overrides):
    """Return a new ChatBannedRights with every flag copied from ``rights``.

    ``overrides`` replaces individual flags. Passing ``rights=None`` yields an
    all-allowed object, which is the correct representation of "this group has
    no default restrictions yet".
    """
    values = {
        flag: bool(getattr(rights, flag, None)) if rights is not None else False
        for flag in BANNED_RIGHT_FLAGS
    }
    values.update({flag: bool(value) for flag, value in overrides.items()})
    return types.ChatBannedRights(
        until_date=getattr(rights, "until_date", None) if rights is not None else None,
        **values,
    )


def describe_rights(rights):
    """Compact, log-friendly view of the flags that are currently banned."""
    if rights is None:
        return "None"
    banned = [flag for flag in BANNED_RIGHT_FLAGS if getattr(rights, flag, None)]
    return ",".join(banned) if banned else "<no restrictions>"


class GroupActions:

    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

    @staticmethod
    def _peer_id_candidates(chat_id):
        """Resolve storage's short channel ID to SPlusthon's full -100 ID."""
        try:
            raw_id = int(chat_id)
            short_id = int(normalize_group_id(chat_id))
        except (TypeError, ValueError):
            return (chat_id,)

        full_channel_id = -(CHANNEL_ID_OFFSET + short_id)
        candidates = [full_channel_id]
        if raw_id not in candidates:
            candidates.append(raw_id)
        return tuple(candidates)

    async def _group_peer(self, chat_id):
        """Use the legacy InputPeer resolution path without get_entity()."""
        last_error = None
        for candidate_id in self._peer_id_candidates(chat_id):
            try:
                peer = await self.client.get_input_entity(candidate_id)
                self.logger.log_info(
                    f"GROUP PEER RESOLVED chat_id={chat_id} resolved_chat_id={candidate_id} "
                    f"peer_type={type(peer).__name__}"
                )
                return peer
            except Exception as error:
                last_error = error
                self.logger.log_info(
                    f"GROUP PEER RESOLVE RETRY chat_id={chat_id} candidate_id={candidate_id} "
                    f"error={error!r}"
                )
        raise ValueError(
            f"Group peer could not be resolved for chat_id={chat_id}; "
            f"candidates={self._peer_id_candidates(chat_id)}"
        ) from last_error

    async def _fetch_default_banned_rights(self, chat_id, peer):
        """Read the group's *current* default rights straight from the server.

        ``get_entity()`` may answer from the local session cache, and a stale
        answer would make us write back outdated flags. So the authoritative
        sources are queried first, cache-backed lookups only as a last resort.

        Returns ``(rights, source)``. ``rights`` may be ``None`` when the group
        genuinely has no default restrictions configured.
        """
        attempts = []

        if hasattr(peer, "channel_id") and hasattr(peer, "access_hash"):
            input_channel = types.InputChannel(peer.channel_id, peer.access_hash)

            async def from_full_channel():
                result = await self.client(
                    functions.channels.GetFullChannelRequest(input_channel)
                )
                for chat in getattr(result, "chats", ()) or ():
                    if getattr(chat, "id", None) == peer.channel_id:
                        return chat
                chats = getattr(result, "chats", ()) or ()
                return chats[0] if chats else None

            async def from_get_channels():
                result = await self.client(
                    functions.channels.GetChannelsRequest([input_channel])
                )
                chats = getattr(result, "chats", ()) or ()
                return chats[0] if chats else None

            attempts.append(("channels.GetFullChannel", from_full_channel))
            attempts.append(("channels.GetChannels", from_get_channels))

        elif hasattr(peer, "chat_id"):

            async def from_get_chats():
                result = await self.client(
                    functions.messages.GetChatsRequest([peer.chat_id])
                )
                chats = getattr(result, "chats", ()) or ()
                return chats[0] if chats else None

            attempts.append(("messages.GetChats", from_get_chats))

        async def from_get_entity():
            return await self.client.get_entity(chat_id)

        attempts.append(("get_entity", from_get_entity))

        last_error = None
        for source, operation in attempts:
            try:
                chat = await operation()
            except Exception as error:
                last_error = error
                self.logger.log_info(
                    f"RIGHTS FETCH RETRY chat_id={chat_id} source={source} error={error!r}"
                )
                continue

            if chat is None:
                self.logger.log_info(
                    f"RIGHTS FETCH EMPTY chat_id={chat_id} source={source}"
                )
                continue

            rights = getattr(chat, "default_banned_rights", None)
            self.logger.log_info(
                f"RIGHTS FETCH OK chat_id={chat_id} source={source} "
                f"chat_type={type(chat).__name__} banned=[{describe_rights(rights)}]"
            )
            return rights, source

        raise ValueError(
            f"default_banned_rights could not be read for chat_id={chat_id}"
        ) from last_error

    async def _set_send_messages_banned(self, chat_id, banned):
        """Flip only ``send_messages``; write every other flag back unchanged."""
        peer = await self._group_peer(chat_id)
        current, source = await self._fetch_default_banned_rights(chat_id, peer)
        updated = clone_banned_rights(current, send_messages=banned)

        changed = [
            flag
            for flag in BANNED_RIGHT_FLAGS
            if bool(getattr(current, flag, None) if current is not None else False)
            != bool(getattr(updated, flag))
        ]
        self.logger.log_info(
            f"RIGHTS DIFF chat_id={chat_id} source={source} "
            f"before=[{describe_rights(current)}] after=[{describe_rights(updated)}] "
            f"changed={changed or ['<none>']}"
        )
        if changed not in ([], ["send_messages"]):
            # Defensive guard: never ship a request that touches another right.
            raise ValueError(
                f"Refusing to edit rights for chat_id={chat_id}: "
                f"unexpected changed flags {changed}"
            )

        return await self.client(
            functions.messages.EditChatDefaultBannedRightsRequest(
                peer=peer,
                banned_rights=updated,
            )
        ), current

    async def lock_group(self, chat_id, minutes=None):
        """Ban only default ``send_messages`` so normal members cannot write."""
        self.logger.log_info(f"LOCK RPC START chat_id={chat_id}")
        try:
            _result, previous = await self._set_send_messages_banned(chat_id, True)
        except Exception:
            self.logger.log_error(
                f"LOCK RPC FAILED chat_id={chat_id}\n{traceback.format_exc()}"
            )
            raise

        state = _load_lock_state()
        state[normalize_group_id(chat_id)] = {
            "send_messages_banned_before_lock": bool(
                getattr(previous, "send_messages", None)
            ),
            "previous_banned_flags": describe_rights(previous),
        }
        _save_lock_state(state)

        self.logger.log_info(f"LOCK RPC SUCCESS chat_id={chat_id}")
        return True

    async def unlock_group(self, chat_id):
        """Clear only the default ``send_messages`` ban."""
        self.logger.log_info(f"UNLOCK RPC START chat_id={chat_id}")
        try:
            await self._set_send_messages_banned(chat_id, False)
        except Exception:
            self.logger.log_error(
                f"UNLOCK RPC FAILED chat_id={chat_id}\n{traceback.format_exc()}"
            )
            raise

        state = _load_lock_state()
        state.pop(normalize_group_id(chat_id), None)
        _save_lock_state(state)

        self.logger.log_info(f"UNLOCK RPC SUCCESS chat_id={chat_id}")
        return True

    async def change_title(self, chat_id, title):
        chat = await self.client.get_input_entity(chat_id)
        await self.client(EditTitleRequest(chat, title))

    async def change_photo(self, chat_id, file_path):
        chat = await self.client.get_input_entity(chat_id)
        uploaded = await self.client.upload_file(file_path)

        from splusthon.tl.types import InputChatUploadedPhoto

        await self.client(
            EditPhotoRequest(chat, InputChatUploadedPhoto(file=uploaded))
        )
