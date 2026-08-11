"""
اقدامات مدیریتی - حذف، سایلنت، بن
"""
import asyncio
import re
from modules.group_stats import add_deleted
from datetime import timedelta

try:
    from splusthon.errors import ChatAdminRequiredError, UserAdminInvalidError
except ImportError:
    # برای زمانی که کتابخانه نصب نیست، کلاس‌های ساختگی
    class ChatAdminRequiredError(Exception): pass
    class UserAdminInvalidError(Exception): pass


def _is_flood_wait(error):
    name = error.__class__.__name__.lower()
    return "flood" in name or ("wait" in name and "second" in str(error).lower())


class AdminActions:
    def __init__(self, client, logger, config_manager):
        self.client = client
        self.logger = logger
        self.config = config_manager

    async def _run_moderation_with_timeout(self, action, user_id, timeout_seconds, operation):
        """حد بالای عملیات؛ FloodWait را برای worker نگه می‌دارد."""
        try:
            return await asyncio.wait_for(operation, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.logger.log_error(
                f"MODERATION ACTION TIMEOUT action={action} user_id={user_id} "
                f"timeout_seconds={timeout_seconds}"
            )
            return False
        except Exception as error:
            if _is_flood_wait(error):
                raise
            raise

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
        return await self._run_moderation_with_timeout(
            "mute", user_id, 45, self._mute_user_rpc(chat_id, user_id, duration_seconds)
        )

    async def _mute_user_rpc(self, chat_id, user_id, duration_seconds=None):
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
            if _is_flood_wait(e):
                raise
            print("MUTE ERROR:", repr(e))
            self.logger.log_error(f"خطا در سکوت کاربر: {e}")
            return False

    async def unmute_user(self, chat_id, user_id) -> bool:
        return await self._run_moderation_with_timeout(
            "unmute", user_id, 15, self._unmute_user_rpc(chat_id, user_id)
        )

    async def _unmute_user_rpc(self, chat_id, user_id) -> bool:
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
            if _is_flood_wait(e):
                raise
            self.logger.log_error(f"خطا در unmute {user_id}: {e}")
            return False


    async def ban_user(self, chat_id, user_id, reason="حذف دائمی به دلیل اسپم") -> bool:
        return await self._run_moderation_with_timeout(
            "ban", user_id, 45, self._ban_user_rpc(chat_id, user_id, reason)
        )

    async def _ban_user_rpc(self, chat_id, user_id, reason="حذف دائمی به دلیل اسپم") -> bool:
        """بن دائمی و ثبت پایدار کاربر برای جلوگیری از بازگشت."""
        try:
            user = await self.client.get_entity(user_id)
            me = await self.client.get_me()
            if getattr(user, "id", user_id) == getattr(me, "id", None):
                self.logger.log_error(
                    "LEAVE REQUEST DEBUG\n"
                    f"chat_id={chat_id}\n"
                    "reason=blocked self-targeted ban\n"
                    "trigger_file=modules/admin_actions.py\n"
                    "trigger_function=AdminActions.ban_user"
                )
                return False

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
                if _is_flood_wait(permission_error):
                    raise
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
            if _is_flood_wait(e):
                raise
            self.logger.log_error(f"خطا در بن دائمی {user_id}: {e}")
            return False

    async def send_warning(self, chat_id, username: str, reason: str, count: int,
                           threshold: int, reply_to=None, user=None):
        """ارسال هشدار با قالب کوتاه و entityهای واقعی SPlus."""
        if not self.config.get("send_warning", True):
            return
        try:
            from splusthon.tl.types import MessageEntityBlockquote, MessageEntityBold

            actual_username = getattr(user, "username", None) if user is not None else username
            first = getattr(user, "first_name", None) if user is not None else None
            last = getattr(user, "last_name", None) if user is not None else None
            display = " ".join(x for x in (first, last) if x).strip()
            name = (f"@{str(actual_username).lstrip('@')}" if actual_username
                    else display or "کاربر ناشناس")
            raw_reason = str(reason or "نامشخص").strip()
            banned_match = re.match(r"^کلمه ممنوعه\s*\((.*?)\)$", raw_reason)
            group_filter_match = re.match(r"^فیلتر گروه\s*\((.*?)\)$", raw_reason)
            if banned_match:
                reason_line = f"دلیل کلمه ممنوعه : ({banned_match.group(1)})"
            elif group_filter_match:
                reason_line = f"دلیل فیلتر گروه : ({group_filter_match.group(1)})"
            else:
                reason_line = f"دلیل فیلتر گروه : {raw_reason}"
            digits = str(count).translate(str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"))
            max_digits = str(threshold).translate(str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"))
            prefix = f"⚠️ کاربر {name}\n"
            body = f"پیام شما حذف شد | {reason_line}\n"
            warning_label = "تعداد اخطار:"
            suffix = f" {digits}/{max_digits}"
            # Keep one completely empty line between the reason and warning count.
            msg = prefix + body + "\n" + warning_label + suffix
            u16 = lambda value: len(value.encode("utf-16-le")) // 2
            entities = [
                MessageEntityBlockquote(offset=0, length=u16(prefix)),
                MessageEntityBold(offset=u16(prefix + body), length=u16(warning_label)),
            ]
            await self.client.send_message(
                chat_id, msg, reply_to=reply_to, formatting_entities=entities)
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
        return await self._run_moderation_with_timeout(
            "unban", user_id, 20, self._unban_user_rpc(chat_id, user_id, username)
        )

    async def _unban_user_rpc(self, chat_id, user_id, username=None):
        try:
            from modules.banned_storage import (
                is_banned,
                remove_banned_everywhere,
            )
            from splusthon.tl import functions, types

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

            display_name = " ".join(
                part for part in (
                    getattr(user, "first_name", None),
                    getattr(user, "last_name", None),
                ) if part
            ).strip()
            removed_count, before_records, remaining_records = (
                remove_banned_everywhere(user_id, username, display_name)
            )
            still_banned = is_banned(chat_id, user_id, username)
            print(
                "UNBAN DEBUG BEFORE "
                f"user_id={user_id} username={username} records={before_records}"
            )
            print(
                "UNBAN DEBUG AFTER "
                f"user_id={user_id} remaining={remaining_records} "
                f"is_banned={still_banned}"
            )
            self.logger.log_info(
                "UNBAN DEBUG "
                f"user_id={user_id} username={username} "
                f"removed={removed_count} is_banned={still_banned}"
            )
            if still_banned or remaining_records:
                self.logger.log_error(
                    f"رکورد بن {user_id} پس از آزادسازی هنوز در ذخیره‌سازی باقی مانده است"
                )
                return False

            self.logger.log_action(
                "UNBAN",
                user_id,
                chat_id,
                "رفع بن دائمی"
            )

            return True

        except Exception as e:
            if _is_flood_wait(e):
                raise
            self.logger.log_error(f"خطا در unban {user_id}: {e}")
            return False
