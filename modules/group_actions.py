"""Administrative group actions that preserve unrelated default permissions."""
import json
from copy import copy
from pathlib import Path

from splusthon.tl import functions, types
from splusthon.tl.functions.channels import EditPhotoRequest, EditTitleRequest


_LOCK_STATE_FILE = Path(__file__).resolve().parent.parent / "config" / "group_message_lock_state.json"


def _load_lock_state():
    try:
        return json.loads(_LOCK_STATE_FILE.read_text(encoding="utf-8")) if _LOCK_STATE_FILE.exists() else {}
    except (OSError, ValueError):
        return {}


def _save_lock_state(data):
    _LOCK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOCK_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class GroupActions:

    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

    async def _input_peer_and_rights(self, chat_id):
        """Resolve an InputPeer, then fetch default rights without get_entity().

        get_entity(chat_id) relies on the client's entity cache and can raise a
        KeyError for numeric group IDs. Raw GetChannels/GetChats requests work
        from the resolved peer and return the current server-side rights.
        """
        peer = await self.client.get_input_entity(chat_id)
        if hasattr(peer, "channel_id") and hasattr(peer, "access_hash"):
            input_channel = types.InputChannel(peer.channel_id, peer.access_hash)
            result = await self.client(functions.channels.GetChannelsRequest([input_channel]))
        elif hasattr(peer, "chat_id"):
            result = await self.client(functions.messages.GetChatsRequest([peer.chat_id]))
        else:
            raise ValueError(f"Unsupported group peer for permission update: {peer!r}")

        chats = getattr(result, "chats", ())
        if not chats:
            raise ValueError(f"Group rights could not be resolved for chat_id={chat_id}")
        rights = getattr(chats[0], "default_banned_rights", None)
        if rights is None:
            # No default restrictions exist. Keep every other permission unset.
            rights = types.ChatBannedRights(until_date=None)
        return peer, copy(rights)

    async def _set_send_messages(self, chat_id, banned):
        """Change only send_messages; all other ChatBannedRights flags are copied."""
        peer, rights = await self._input_peer_and_rights(chat_id)
        rights.send_messages = bool(banned)
        return await self.client(
            functions.messages.EditChatDefaultBannedRightsRequest(
                peer=peer,
                banned_rights=rights,
            )
        )

    async def lock_group(self, chat_id, minutes=None):
        # Capture the exact previous bit before changing it.
        _peer, rights = await self._input_peer_and_rights(chat_id)
        state = _load_lock_state()
        state[str(chat_id)] = {"send_messages_banned": bool(rights.send_messages)}
        _save_lock_state(state)
        await self._set_send_messages(chat_id, banned=True)
        self.logger.log_info(f"GROUP MESSAGE LOCKED chat_id={chat_id}")
        return True

    async def unlock_group(self, chat_id):
        # Restore only the bit recorded by lock_group. For old locks without a
        # record, enable just text messages and leave every other right intact.
        state = _load_lock_state()
        previous = state.pop(str(chat_id), {}).get("send_messages_banned", False)
        _save_lock_state(state)
        await self._set_send_messages(chat_id, banned=previous)
        self.logger.log_info(
            f"GROUP MESSAGE UNLOCKED chat_id={chat_id} restored_banned={previous}"
        )
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
