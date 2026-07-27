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

    async def _default_banned_rights(self, chat_id):
        """Fetch a copy of the current default rights, never a blank allow-all set."""
        chat = await self.client.get_entity(chat_id)
        rights = getattr(chat, "default_banned_rights", None)
        if rights is None:
            # No default restrictions exist, so only the requested flag is needed.
            rights = types.ChatBannedRights(until_date=None)
        return copy(rights)

    async def _set_send_messages(self, chat_id, banned):
        """Change only ChatBannedRights.send_messages and preserve every other flag."""
        rights = await self._default_banned_rights(chat_id)
        rights.send_messages = bool(banned)
        peer = await self.client.get_input_entity(chat_id)
        return await self.client(
            functions.messages.EditChatDefaultBannedRightsRequest(
                peer=peer,
                banned_rights=rights,
            )
        )

    async def lock_group(self, chat_id, minutes=None):
        # Save the old send-messages bit. It may already be restricted by the group.
        rights = await self._default_banned_rights(chat_id)
        state = _load_lock_state()
        state[str(chat_id)] = {"send_messages_banned": bool(rights.send_messages)}
        _save_lock_state(state)
        await self._set_send_messages(chat_id, banned=True)
        self.logger.log_info(f"GROUP MESSAGE LOCKED chat_id={chat_id}")
        return True

    async def unlock_group(self, chat_id):
        # Restore exactly the value captured by lock_group. If this bot has no
        # captured state (for example an old lock), enable only text messages.
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

        await self.client(
            EditTitleRequest(
                chat,
                title,
            )
        )

    async def change_photo(self, chat_id, file_path):
        chat = await self.client.get_input_entity(chat_id)
        uploaded = await self.client.upload_file(file_path)

        from splusthon.tl.types import InputChatUploadedPhoto

        await self.client(
            EditPhotoRequest(
                chat,
                InputChatUploadedPhoto(
                    file=uploaded,
                )
            )
        )
