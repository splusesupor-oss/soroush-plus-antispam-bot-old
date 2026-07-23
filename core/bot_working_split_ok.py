from modules.security.security_manager import check_security, remove_message
from modules.security.attack_guard import check_attack, clear_attack
from modules.security.delete_queue import process_delete
import asyncio
from modules.admin_storage import is_admin, add_admin, remove_admin
from modules.riddles import new_riddle, check_answer, get_answer
from modules.group_stats import add_message, add_deleted, add_kick, add_mute, make_report
from modules import ConfigManager, SpamDetector, BotLogger, UserTracker, AdminActions
from modules.jorat_haghighat import get_jorat, get_haghighat
from modules.font_converter import make_fonts
from modules.owner_check import is_global_owner, normalize_username
from modules.banned_storage import (
    add_banned,
    remove_banned,
    is_banned,
    load_banned,
    get_matching_ban_records,
    remove_banned_everywhere,
    FILE as BANNED_STORAGE_FILE,
)
from modules.group_words_commands import handle_group_word_command
from modules.group_banned_words_control import enable, disable
from modules.group_storage import activate_group, deactivate_group, get_group_owner, is_active
from modules.group_actions import GroupActions
from handlers.message_handler import handle_new_message, send_activation_message
from handlers.admin_handler import handle_admin_commands
import random
"""
ربات مدیریت گروه سروش پلاس - ضد هرزنامه
اجرا روی حساب کاربری شما با SPlusthon (فورک Telethon برای سروش)

ویژگی‌ها:
- بررسی تمام پیام‌های جدید گروه
- تشخیص لینک، شماره، آیدی، کلمات تبلیغاتی
- حذف خودکار + سایلنت/بن بعد از 3 تخلف
- وایت لیست مدیران
- افزودن کلمات ممنوعه از طریق فایل یا دستور
- لاگ کامل
- ماژولار

نویسنده: Agent for Soroush Plus
"""

import os
import asyncio
import sys
from dotenv import load_dotenv
from splusthon.tl.types import MessageEntityBold, MessageEntityBlockquote

# لود env
load_dotenv()

# اگر پوشه ماژول‌ها در مسیر نیست اضافه کن
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# تلاش برای import SPlusthon
try:
    from splusthon import SoroushClient, events
    from splusthon.sessions import StringSession
    SPLUSTHON_AVAILABLE = True
except ImportError:
    SPLUSTHON_AVAILABLE = False
    print("⚠️ کتابخانه splusthon نصب نیست. ابتدا pip install splusthon را اجرا کنید")
    print("راهنما: pip install -r requirements.txt")


from splusthon import types
global functions

from splusthon.tl import functions
from collections import defaultdict, deque
# ---------------------------------------------------


class SoroushAntiSpamBot:
    def __init__(self, config_path="config/config.json"):
        print("🚀 در حال بارگذاری تنظیمات...")
        self.config_manager = ConfigManager(config_path=config_path)
        self.bot_sent_messages = []
        self.logger = BotLogger(
            log_file=self.config_manager.get(
                "log_file", "logs/deleted_messages.log"))
        self.detector = SpamDetector(self.config_manager)
        self.tracker = UserTracker(
            spam_counts_file=self.config_manager.get(
                "spam_counts_file",
                "logs/spam_counts.json"),
            threshold=self.config_manager.get(
                "spam_threshold",
                3))

        self.client = None
        self.admin_actions = None
        self.group_actions = None
        self.delete_notice_lock = set()
        self.punished_users = set()
        self.repeat_messages = {}
        self.flood_messages = {}
        self.user_messages = {}
        self.group_timer_tasks = {}
        self.spam_burst_users = set()
        self.spam_burst_messages = {}
        self.spam_burst_tasks = {}
        from modules.delete_queue import process_delete
        self.process_delete = process_delete

        self.logger.log_info("✅ تنظیمات بارگذاری شد")
        self.logger.log_info(
            f"📚 تعداد کلمات ممنوعه: {len(self.config_manager.banned_words)}")
        self.logger.log_info(
            f"🛡️ تعداد کاربران سفید: {len(self.config_manager.whitelisted_ids)}")

    async def initialize_client(self):
        """ساخت کلاینت سروش"""
        if not SPLUSTHON_AVAILABLE:
            raise RuntimeError("SPlusthon نصب نیست")

        # اولویت: SESSION_STRING از env یا config
        session_str = os.getenv("SOROUSH_SESSION_STRING") or self.config_manager.get(
            "session_string", "")
        api_id = os.getenv("API_ID") or self.config_manager.get("api_id")
        api_hash = os.getenv("API_HASH") or self.config_manager.get("api_hash")

        # اگر session string وجود داشته باشد از آن استفاده کن
        if session_str:
            session = StringSession(session_str)
        else:
            session = StringSession()  # جدید می‌سازد و بعد باید ذخیره کنی

        # SPlusthon شامل api_id/hash پیش‌فرض برای سروش است، ولی اگر کاربر
        # مقادیر شخصی دارد استفاده می‌کنیم
        if api_id and api_hash:
            self.client = SoroushClient(session, api_id, api_hash)
        else:
            self.client = SoroushClient(session)

        self.spammer_messages = defaultdict(lambda: deque(maxlen=5000))

        self.admin_actions = AdminActions(
            self.client, self.logger, self.config_manager)

        self.group_actions = GroupActions(
            self.client, self.logger)
        return self.client



    async def check_group_word_commands(self, event, text, chat_id, user_id):
        try:
            print("FILTER ARGS:", repr(text), type(text), chat_id, user_id)
            return await handle_group_word_command(
                self,
                event,
                text,
                chat_id,
                user_id
            )
        except Exception as e:
            self.logger.log_error(f"خطای فیلتر کلمه: {e}")
            return False


    async def is_admin_user(self, event, user_id):
        try:
            sender = await event.get_sender()
            username = getattr(sender, "username", None)

            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None)

            if is_admin(chat_id, user_id):
                return True

            if is_global_owner(username):
                return True

            return False

        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False

    async def run(self):
        """اجرای ربات"""
        await self.initialize_client()

        await self.client.connect()
        asyncio.create_task(process_delete(self))

        async def is_currently_restricted(chat_id, user):
            """وضعیت فعلی عضو را از SPlusthon می‌خواند؛ خطا یعنی حفظ بن فعلی."""
            try:
                channel = await self.client.get_input_entity(chat_id)
                participant = await self.client.get_input_entity(user)
                result = await self.client(
                    functions.channels.GetParticipantRequest(
                        channel=channel,
                        participant=participant,
                    )
                )
                state = getattr(result, "participant", None)
                state_name = state.__class__.__name__ if state else "Unknown"
                restricted = "Banned" in state_name
                self.logger.log_info(
                    f"MANUAL RELEASE CHECK user_id={getattr(user, 'id', None)} "
                    f"state={state_name} restricted={restricted}"
                )
                return restricted
            except Exception as error:
                self.logger.log_error(
                    f"خطا در بررسی وضعیت بن کاربر {getattr(user, 'id', None)}: {error}"
                )
                return True


        @self.client.on(events.Raw(types.UpdateChannelParticipant))
        async def manual_unban_update(update):
            previous = getattr(update, "prev_participant", None)
            current = getattr(update, "new_participant", None)
            previous_name = previous.__class__.__name__ if previous else "None"
            current_name = current.__class__.__name__ if current else "None"

            if "Banned" not in previous_name or "Banned" in current_name:
                return

            chat_id = getattr(update, "channel_id", None)
            user_id = getattr(update, "user_id", None)
            if chat_id is None or user_id is None:
                return

            try:
                user = await self.client.get_entity(user_id)
                username = getattr(user, "username", None)
                display_name = " ".join(
                    part for part in (
                        getattr(user, "first_name", None),
                        getattr(user, "last_name", None),
                    ) if part
                ).strip()
                if not is_banned(chat_id, user_id, username, data=load_banned()):
                    return

                removed_count, _, remaining_records = remove_banned_everywhere(
                    user_id,
                    username,
                    display_name,
                )
                self.tracker.banned_users.pop(f"{chat_id}:{user_id}", None)
                self.punished_users.discard(f"{chat_id}:{user_id}")
                self.spammer_messages.pop(user_id, None)
                self.logger.log_info(
                    "Detected manual release, removed user from permanent "
                    f"banned storage. user_id={user_id} "
                    f"update={previous_name}->{current_name} "
                    f"removed={removed_count} remaining={remaining_records}"
                )
            except Exception as error:
                self.logger.log_error(
                    f"خطا در همگام‌سازی آزادسازی دستی {user_id}: {error}"
                )


        @self.client.on(events.ChatAction())
        async def banned_join_check(event):
            try:
                if not event.user_joined and not event.user_added:
                    return

                user = await event.get_user()
                if not user:
                    return

                chat_id = event.chat_id
                if not is_active(chat_id):
                    return

                user_id = user.id
                username = getattr(user, "username", None)

                banned_data = load_banned()
                banned = is_banned(
                    chat_id, user_id, username, data=banned_data
                )
                matching_records = get_matching_ban_records(
                    chat_id, user_id, username, data=banned_data
                )
                self.logger.log_info(
                    "JOIN BAN CHECK "
                    f"user_id={user_id} username={username} is_banned={banned} "
                    f"file={BANNED_STORAGE_FILE} records={matching_records}"
                )
                print(
                    "JOIN BAN DEBUG "
                    f"user_id={user_id} username={username} "
                    f"source={BANNED_STORAGE_FILE} records={matching_records}"
                )
                if banned:
                    if not await is_currently_restricted(chat_id, user):
                        display_name = " ".join(
                            part for part in (
                                getattr(user, "first_name", None),
                                getattr(user, "last_name", None),
                            ) if part
                        ).strip()
                        removed_count, _, remaining_records = (
                            remove_banned_everywhere(
                                user_id,
                                username,
                                display_name,
                            )
                        )
                        self.tracker.banned_users.pop(
                            f"{chat_id}:{user_id}", None
                        )
                        self.punished_users.discard(f"{chat_id}:{user_id}")
                        self.spammer_messages.pop(user_id, None)
                        self.logger.log_info(
                            "Detected manual release, removed user from permanent "
                            f"banned storage. user_id={user_id} "
                            f"removed={removed_count} remaining={remaining_records}"
                        )
                        return

                    await self.client.edit_permissions(
                        chat_id,
                        user,
                        until_date=None,
                        view_messages=False
                    )

                    print(
                        f"🚫 blocked banned user rejoin: {user_id}"
                    )

            except Exception as e:
                print(f"join ban check error: {e}")


        @self.client.on(events.NewMessage())
        async def new_message_handler(event):

            if event.out:
                return

            text = (event.message.message or "").strip()

            # MASTER GROUP MODE GATE: every incoming group message passes here first.
            if not event.is_private:
                chat_lock = await event.get_chat()
                lock_id = getattr(chat_lock, "id", None)
                sender_lock = await event.get_sender()
                sender_id = getattr(sender_lock, "id", None)
                registered_owner_id = get_group_owner(lock_id)
                group_is_active = is_active(lock_id)
                sender_username = getattr(sender_lock, "username", None)
                normalized_username = normalize_username(sender_username)
                is_registered_owner = (
                    registered_owner_id is not None
                    and str(sender_id) == str(registered_owner_id)
                )
                is_global_bot_owner = is_global_owner(sender_username)
                can_change_group_mode = (
                    is_global_bot_owner or is_registered_owner
                )
                is_enable_command = text == "فعال"
                is_disable_command = text == "غیر فعال"

                if is_enable_command or is_disable_command:
                    self.logger.log_info(
                        "GROUP MODE DEBUG "
                        f"chat_id={lock_id} sender_id={sender_id} "
                        f"sender_username={sender_username!r} "
                        f"normalized_username={normalized_username!r} "
                        f"text={text!r} disabled_before={not group_is_active} "
                        f"registered_owner_id={registered_owner_id} "
                        f"registered_owner_check={is_registered_owner} "
                        f"global_owner_check={is_global_bot_owner} "
                        f"mode_owner_check={can_change_group_mode} "
                        f"enable_match={is_enable_command} "
                        f"disable_match={is_disable_command}"
                    )

                if not group_is_active:
                    if is_enable_command and can_change_group_mode:
                        title = getattr(chat_lock, "title", "")
                        activate_group(lock_id, title)
                        await send_activation_message(
                            self, event, lock_id, title
                        )
                    return

                if is_disable_command:
                    if can_change_group_mode:
                        title = getattr(chat_lock, "title", "")
                        deactivate_group(lock_id, title)
                        for task in self.group_timer_tasks.pop(lock_id, set()):
                            task.cancel()
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                        )
                    return

            # آزاد کردن کاربر محروم شده
            if text == "آزاد":
                try:
                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        event.chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    user = await reply_msg.get_sender()
                    if not user:
                        await event.reply("❌ کاربر پیدا نشد")
                        return

                    released = await self.admin_actions.unban_user(
                        event.chat_id,
                        user.id,
                        getattr(user, "username", None)
                    )
                    if not released:
                        await event.reply("❌ آزاد کردن انجام نشد")
                        return

                    self.tracker.banned_users.pop(
                        f"{event.chat_id}:{user.id}", None
                    )
                    self.punished_users.discard(f"{event.chat_id}:{user.id}")
                    burst_key = (event.chat_id, user.id)
                    burst_task = self.spam_burst_tasks.pop(burst_key, None)
                    if burst_task:
                        burst_task.cancel()
                    self.spam_burst_users.discard(burst_key)
                    self.spam_burst_messages.pop(burst_key, None)
                    self.spammer_messages.pop(user.id, None)
                    self.logger.log_info(
                        f"UNBAN COMPLETE user_id={user.id} removed successfully"
                    )
                    await event.reply("♻️ کاربر آزاد شد")

                except Exception as e:
                    await event.reply(f"❌ خطا در آزاد کردن: {e}")
                return



              # پیوی فقط دستور صفر کردن تخلف
            if event.is_private:
                text = (event.message.message or "").strip()

                if "صفر" in text:
                    sender = await event.get_sender()
                    if not is_global_owner(getattr(sender, "username", None)):
                        await event.reply(
                            "❌ فقط مالک اصلی ربات اجازه استفاده از این دستور را دارد"
                        )
                        return
                    try:
                        import re
                        from modules.group_storage import load_groups

                        m = re.search(r"@([A-Za-z0-9_]+)", text)
                        if not m:
                            await event.reply("❌ آیدی کاربر پیدا نشد")
                            return

                        username = m.group(1)

                        groups = load_groups()
                        if not groups:
                            await event.reply("❌ هیچ گروهی ثبت نشده")
                            return

                        import json

                        with open("logs/user_map.json", "r", encoding="utf-8") as f:
                            user_map = json.load(f)

                        user_id = None

                        for gid, users in user_map.items():
                            for uname, uid in users.items():
                                if str(uname).lower() == username.lower():
                                    user_id = int(uid)
                                    break
                            if user_id:
                                break

                        if not user_id:
                            await event.reply("❌ کاربر در لیست ثبت شده پیدا نشد")
                            return

                        reset_groups = []
                        all_counts = self.tracker.get_all_counts()

                        for gid, users in all_counts.items():
                            if str(user_id) in users or user_id in users:
                                self.tracker.reset_count(int(gid), user_id)
                                reset_groups.append(gid)

                                try:
                                    await self.client.send_message(
                                        int(gid),
                                        f"✅ تخلفات @{username} صفر شد"
                                    )
                                except Exception as send_err:
                                    self.logger.log_error(
                                        f"خطای ارسال پیام صفر کردن در گروه {gid}: {send_err}"
                                    )

                        if not reset_groups:
                            await event.reply("❌ این کاربر هیچ تخلف ثبت شده‌ای ندارد")
                            return

                        await event.reply("✅ انجام شد")

                    except Exception as e:
                        self.logger.log_error(
                            f"خطای صفر کردن از پیوی: {e}"
                        )

                return

            
                # اجرای دستورات مدیریتی
                if text.startswith(("!", "/", ".")):
                    try:
                        sender = await event.get_sender()
                        await handle_admin_commands(
                            self,
                            event,
                            text,
                            getattr(sender, "id", 0),
                            event.chat_id
                        )
                        return
                    except Exception as e:
                        self.logger.log_error(f"خطای اجرای دستور مدیر: {e}")

            await handle_new_message(self, event)


        print("✅ ربات فعال شد و منتظر پیام است")

        await self.client.run_until_disconnected()


    # ---------- SPAM HISTORY STORAGE ----------
    async def remember_spam_message(self, user_id, message_id):
        try:
            if not hasattr(self, "spammer_messages"):
                self.spammer_messages = {}

            if user_id not in self.spammer_messages:
                self.spammer_messages[user_id] = []

            self.spammer_messages[user_id].append(message_id)

        except Exception as e:
            print("remember spam error:", e)


    async def delete_all_spam_messages(self, user_id):
        try:
            ids = []

            if hasattr(self, "spammer_messages"):
                ids = list(self.spammer_messages.get(user_id, []))

            if ids:
                await self.client.delete_messages(ids)

            if hasattr(self, "spammer_messages"):
                self.spammer_messages.pop(user_id, None)

        except Exception as e:
            print("delete spam error:", e)


        await self.client.run_until_disconnected()




