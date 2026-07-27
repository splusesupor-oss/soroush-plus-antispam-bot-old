"""Administrative actions using the SPlusthon method used by this bot's working history."""
from splusthon.tl.functions.channels import (
    EditPhotoRequest,
    ToggleJoinToSendRequest,
    EditTitleRequest,
)

from modules.group_id import CHANNEL_ID_OFFSET, normalize_group_id


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

    async def lock_group(self, chat_id, minutes=None):
        """Restore the project's original SPlusthon lock request.

        ToggleJoinToSendRequest changes only the join-to-send mode; it does not
        construct, reset, or allow any ChatBannedRights permission flags.
        """
        peer = await self._group_peer(chat_id)
        await self.client(ToggleJoinToSendRequest(peer, True))
        self.logger.log_info(f"GROUP LOCKED chat_id={chat_id} mode=join_to_send")
        return True

    async def unlock_group(self, chat_id):
        """Restore the original matching unlock request without touching rights."""
        peer = await self._group_peer(chat_id)
        await self.client(ToggleJoinToSendRequest(peer, False))
        self.logger.log_info(f"GROUP UNLOCKED chat_id={chat_id} mode=join_to_send")
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
