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
        # SPlusthon user=None updates default member permissions for the group.
        await self.client.edit_permissions(
            chat_id,
            None,
            send_messages=False,
            send_media=False,
            send_stickers=False,
            send_gifs=False,
            send_games=False,
            send_inline=False,
            send_polls=False,
        )

    async def unlock_group(self, chat_id):
        await self.client.edit_permissions(
            chat_id,
            None,
            send_messages=True,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_games=True,
            send_inline=True,
            send_polls=True,
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
