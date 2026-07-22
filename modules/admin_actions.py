"""
اقدامات مدیریتی - حذف، سایلنت، بن
"""
import asyncio
from modules.group_stats import add_deleted
from datetime import timedelta

try:
    from splusthon.errors import ChatAdminRequiredError, UserAdminInvalidError
except ImportError:
    # برای زمانی که کتابخانه نصب نیست، کلاس‌های ساختگی
    class ChatAdminRequiredError(Exception): pass
    class UserAdminInvalidError(Exception): pass


class AdminActions:
    def __init__(self, client, logger, config_manager):
        self.client = client
        self.logger = logger
        self.config = config_manager

    async def delete_message(self, chat_id, message_id=None, event=None) -> bool:
        """حذف پیام"""
        try:
            if event and hasattr(event, 'delete'):
                await event.delete()
                return True
            elif message_id:
                await self.client.delete_messages(chat_id, message_id)

                try:
                    add_deleted(chat_id, 0, "system")
                except Exception:
                    pass

                return True
        except ChatAdminRequiredError:
            self.logger.log_error(f"❌ دسترسی ادمین برای حذف پیام در {chat_id} ندارید")
            return False
        except Exception as e:
            self.logger.log_error(f"خطا در حذف پیام {message_id} در {chat_id}: {e}")
            return False
        return False

    async def mute_user(self, chat_id, user_id, duration_seconds=None):
        try:
            from datetime import datetime, timedelta, timezone
            from splusthon import types
            from splusthon.tl import functions

            user = await self.client.get_input_entity(user_id)
            chat = await self.client.get_input_entity(chat_id)

            until_date = None if duration_seconds is None else datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

            rights = types.ChatBannedRights(
                until_date=until_date,
                view_messages=False,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )

            await self.client(functions.channels.EditBannedRequest(
                channel=chat,
                participant=user,
                banned_rights=rights
            ))

            self.logger.log_action(
                "MUTE",
                user_id,
                chat_id,
                f"به مدت {duration_seconds} ثانیه"
            )

            return True

        except Exception as e:
            print("MUTE ERROR:", repr(e))
            self.logger.log_error(f"خطا در سکوت کاربر: {e}")
            return False

    async def unmute_user(self, chat_id, user_id) -> bool:
        try:
            user = await self.client.get_entity(user_id)

            await self.client.edit_permissions(
                chat_id,
                user,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                send_polls=True,
                until_date=None
            )

            self.logger.log_action("UNMUTE", user_id, chat_id)
            return True

        except Exception as e:
            self.logger.log_error(f"خطا در unmute {user_id}: {e}")
            return False


    async def ban_user(self, chat_id, user_id, reason="حذف دائمی به دلیل اسپم") -> bool:
        """بن دائمی و ثبت پایدار کاربر برای جلوگیری از بازگشت."""
        try:
            user = await self.client.get_entity(user_id)

            await self.client.kick_participant(
                chat_id,
                user
            )
            try:
                await self.client.edit_permissions(
                    chat_id,
                    user,
                    until_date=None,
                    view_messages=False,
                )
            except Exception as permission_error:
                self.logger.log_error(
                    f"خطا در اعمال محدودیت دائمی {user_id}: {permission_error}"
                )

            try:
                from modules.banned_storage import add_banned

                username = getattr(user, "username", None)
                display_name = " ".join(
                    part for part in (
                        getattr(user, "first_name", None),
                        getattr(user, "last_name", None),
                    ) if part
                ).strip()
                add_banned(
                    chat_id,
                    user_id,
                    username=username,
                    display_name=display_name,
                    reason=reason,
                )

            except Exception as e:
                self.logger.log_error(f"storage ban error: {e}")

            self.logger.log_action(
                "BAN",
                user_id,
                chat_id,
                reason
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در بن دائمی {user_id}: {e}")
            return False

    async def send_warning(self, chat_id, username: str, reason: str, count: int, threshold: int, reply_to=None):
        """ارسال پیام هشدار"""
        if not self.config.get("send_warning", True):
            return
        try:
            template = self.config.get("warning_message", "⚠️ @{username} پیام شما به دلیل {reason} حذف شد.")
            msg = template.format(username=username or "کاربر", reason=reason, count=count, threshold=threshold)
            
            if reply_to:
                await self.client.send_message(chat_id, msg, reply_to=reply_to)
            else:
                await self.client.send_message(chat_id, msg)
        except Exception as e:
            print("WARNING ERROR:", repr(e))
            self.logger.log_error(f"خطا در ارسال هشدار: {e}")

    async def punish_user(
        self, chat_id, user_id, username: str = None, announce: bool = True
    ):
        """اعمال مجازات بر اساس تنظیمات"""
        action = self.config.get("action_on_threshold", "mute")
        duration = self.config.get("action_duration_seconds", 3600)

        if action == "mute":
            success = await self.mute_user(chat_id, user_id, duration)
            if success and announce:
                try:
                    await self.client.send_message(
                        chat_id,
                        f"🔇 کاربر @{username or user_id} به دلیل ارسال {self.config.get('spam_threshold')} هرزنامه مکرر، به مدت {duration//60} دقیقه سایلنت شد."
                    )
                except:
                    pass
            return success
        elif action in ["ban", "kick"]:
            success = await self.ban_user(
                chat_id, user_id, reason="رسیدن به آستانه تخلفات"
            )
            if success and announce:
                try:
                    await self.client.send_message(
                        chat_id,
                        f"⛔️ کاربر @{username or user_id} به دلیل اسپم مکرر از گروه حذف شد."
                    )
                except:
                    pass
            return success
        return False


    async def unban_user(self, chat_id, user_id, username=None):
        try:
            from modules.banned_storage import remove_banned
            from splusthon.tl import functions, types

            remove_banned(chat_id, user_id, username)

            user = await self.client.get_entity(user_id)
            entity = await self.client.get_input_entity(chat_id)
            user_entity = await self.client.get_input_entity(user)

            await self.client(
                functions.channels.EditBannedRequest(
                    channel=entity,
                    participant=user_entity,
                    banned_rights=types.ChatBannedRights(
                        until_date=None,
                        view_messages=False,
                        send_messages=False,
                        send_media=False,
                        send_stickers=False,
                        send_gifs=False,
                        send_games=False,
                        send_inline=False,
                        embed_links=False,
                        send_polls=False,
                        change_info=False,
                        invite_users=False,
                        pin_messages=False
                    )
                )
            )

            self.logger.log_action(
                "UNBAN",
                user_id,
                chat_id,
                "رفع بن دائمی"
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در unban {user_id}: {e}")
            return False
