"""
اقدامات مدیریتی - حذف، سایلنت، بن
"""
import asyncio
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
                return True
        except ChatAdminRequiredError:
            self.logger.log_error(f"❌ دسترسی ادمین برای حذف پیام در {chat_id} ندارید")
            return False
        except Exception as e:
            self.logger.log_error(f"خطا در حذف پیام {message_id} در {chat_id}: {e}")
            return False
        return False

    async def mute_user(self, chat_id, user_id, duration_seconds: int = 3600) -> bool:
        """سایلنت کردن کاربر - محدود کردن ارسال پیام"""
        try:
            # در Telethon/SPlusthon برای mute باید send_messages=False شود
            # تا زمان مشخص
            until_date = None
            if duration_seconds:
                from datetime import datetime, timedelta
                until_date = datetime.now() + timedelta(seconds=duration_seconds)

            # تلاش برای mute
            await self.client.edit_permissions(
                chat_id,
                user_id,
                until_date=until_date,
                send_messages=False
            )
            self.logger.log_action("MUTE", user_id, chat_id, f"به مدت {duration_seconds} ثانیه")
            return True
        except ChatAdminRequiredError:
            self.logger.log_error(f"❌ برای mute کردن {user_id} در {chat_id} دسترسی ادمین لازم است")
            return False
        except Exception as e:
            self.logger.log_error(f"خطا در mute کردن {user_id}: {e}")
            # تلاش جایگزین با روش قدیمی
            try:
                await self.client.edit_permissions(chat_id, user_id, send_messages=False)
                return True
            except Exception as e2:
                self.logger.log_error(f"خطای دوباره mute: {e2}")
                return False

    async def unmute_user(self, chat_id, user_id) -> bool:
        """رفع سایلنت"""
        try:
            await self.client.edit_permissions(
                chat_id,
                user_id,
                send_messages=True
            )
            self.logger.log_action("UNMUTE", user_id, chat_id)
            return True
        except Exception as e:
            self.logger.log_error(f"خطا در unmute {user_id}: {e}")
            return False

    async def ban_user(self, chat_id, user_id) -> bool:
        """حذف / بن کردن کاربر از گروه"""
        try:
            await self.client.kick_participant(chat_id, user_id)
            self.logger.log_action("BAN/KICK", user_id, chat_id, "حذف از گروه به دلیل اسپم مکرر")
            return True
        except ChatAdminRequiredError:
            self.logger.log_error(f"❌ برای بن کردن {user_id} دسترسی ادمین لازم است در {chat_id}")
            return False
        except Exception as e:
            self.logger.log_error(f"خطا در بن کردن {user_id}: {e}")
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
            self.logger.log_error(f"خطا در ارسال هشدار: {e}")

    async def punish_user(self, chat_id, user_id, username: str = None):
        """اعمال مجازات بر اساس تنظیمات"""
        action = self.config.get("action_on_threshold", "mute")
        duration = self.config.get("action_duration_seconds", 3600)

        if action == "mute":
            success = await self.mute_user(chat_id, user_id, duration)
            if success:
                try:
                    await self.client.send_message(
                        chat_id,
                        f"🔇 کاربر @{username or user_id} به دلیل ارسال {self.config.get('spam_threshold')} هرزنامه مکرر، به مدت {duration//60} دقیقه سایلنت شد."
                    )
                except:
                    pass
            return success
        elif action in ["ban", "kick"]:
            success = await self.ban_user(chat_id, user_id)
            if success:
                try:
                    await self.client.send_message(
                        chat_id,
                        f"⛔️ کاربر @{username or user_id} به دلیل اسپم مکرر از گروه حذف شد."
                    )
                except:
                    pass
            return success
        return False
