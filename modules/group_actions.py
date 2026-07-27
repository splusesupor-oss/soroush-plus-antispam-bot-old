from splusthon.tl.functions.channels import (
    EditPhotoRequest,
    ToggleJoinToSendRequest,
    EditTitleRequest
)


class GroupActions:

    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

    async def lock_group(self, chat_id, minutes=None):
        # Only message sending is changed; every unrelated group permission stays intact.
        await self.client.edit_permissions(
            chat_id,
            None,
            send_messages=False,
        )

    async def unlock_group(self, chat_id):
        # Mirror lock_group: re-enable only the permission that lock changed.
        await self.client.edit_permissions(
            chat_id,
            None,
            send_messages=True,
        )

    async def change_title(self, chat_id, title):
        chat = await self.client.get_input_entity(chat_id)

        await self.client(
            EditTitleRequest(
                chat,
                title
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
                    file=uploaded
                )
            )
        )
