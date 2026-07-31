from modules.security.security_manager import check_security, remove_message
from modules.security.attack_guard import check_attack, clear_attack
from modules.security.delete_queue import process_delete
import asyncio
from modules.admin_storage import is_admin, add_admin, remove_admin
from modules.riddles import new_riddle, check_answer, get_answer
from modules.spam_history import get_user_history
from modules.group_stats import add_message, add_deleted, add_kick, add_mute, make_report
from modules import ConfigManager, SpamDetector, BotLogger, UserTracker, AdminActions
from modules.jorat_haghighat import get_jorat, get_haghighat
from modules.font_converter import make_fonts
from modules.owner_check import get_owner, is_global_owner, normalize_username
from modules.group_expiry import match_command as expiry_command
from handlers.economy_handler import handle as handle_economy
from handlers.group_expiry_handler import (
    run_expiry_watcher as run_group_expiry_watcher,
)
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
from modules.group_storage import activate_group, deactivate_group, is_active
from modules.group_storage_migration import migrate_all_group_storage
from modules.group_actions import GroupActions
# 💰 تسویهٔ روزانه از راه API اقتصاد جدید.
from economy import settle_previous_days
from modules.group_stats import flush as flush_group_stats
from modules.user_activity import flush as flush_user_activity
from modules.reminders import due as due_reminders, mark_sent as mark_reminder_sent
from modules.moderation_queue import ModerationQueue
from modules.outgoing_profiler import instrument_client, instrument_event
from handlers.message_handler import handle_new_message, send_activation_message
from handlers.broadcast_handler import handle_private_broadcast
from modules.name_family import cancel_round as cancel_name_family_round
from modules.broadcast_state import (
    BROADCAST_COMMAND_WORDS,
    get as get_broadcast_state,
    is_broadcast_command,
    normalize_command_text,
)
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
import time
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
        migrated_files = migrate_all_group_storage()
        self.config_manager = ConfigManager(config_path=config_path)
        if migrated_files:
            print("GROUP STORAGE MIGRATED:", ", ".join(migrated_files))
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
        self.moderation_queue = ModerationQueue(self.logger)
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
        self.rejoin_spam_state = {}
        self.forward_spam_counts = {}
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
        instrument_client(self.client, self.logger)

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

            if is_admin(chat_id, user_id, username):
                return True

            if is_global_owner(user_id):
                return True

            return False

        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False

    async def run(self):
        """اجرای ربات"""
        await self.initialize_client()

        await self.client.connect()
        try:
            self.bot_account_id = getattr(await self.client.get_me(), "id", None)
        except Exception as error:
            self.bot_account_id = None
            self.logger.log_error(f"خطا در دریافت شناسه حساب ربات: {error}")
        asyncio.create_task(process_delete(self))

        async def settle_daily_coins():
            while True:
                try:
                    awards = settle_previous_days()
                    for chat_id, user_id, amount in awards:
                        self.logger.log_info(
                            f"DAILY COIN AWARD chat_id={chat_id} "
                            f"user_id={user_id} bronze={amount}"
                        )
                except Exception as error:
                    self.logger.log_error(f"خطا در تسویه سکه روزانه: {error}")
                await asyncio.sleep(3600)

        asyncio.create_task(settle_daily_coins())

        async def reminder_loop():
            while True:
                for reminder in due_reminders():
                    try:
                        await self.client.send_message(
                            int(reminder["chat_id"]),
                            "⏰ یادآوری\n\n"
                            f"سلام {reminder['name']} 👋\n\n"
                            f"📝 {reminder['text']}",
                        )
                        mark_reminder_sent(reminder["id"])
                    except Exception as error:
                        self.logger.log_error(
                            f"خطا در ارسال یادآوری {reminder.get('id')}: {error}"
                        )
                flush_group_stats()
                flush_user_activity()
                await asyncio.sleep(15)

        asyncio.create_task(reminder_loop())

        # ⏳ ناظر تاریخ انقضای گروه — کاملاً مستقل از بقیهٔ حلقه‌ها.
        # بدون نیاز به هیچ پیامی، دقیقاً در زمان تعیین‌شده گروه را می‌بندد.
        async def group_expiry_loop():
            def deactivate(group_id, title):
                deactivate_group(group_id, title)
                for task in self.group_timer_tasks.pop(group_id, set()):
                    task.cancel()

            await run_group_expiry_watcher(
                self, deactivate, logger=self.logger)

        asyncio.create_task(group_expiry_loop())

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

        def restore_rejoin_spam_state(chat_id, user_id):
            punish_key = f"{chat_id}:{user_id}"
            burst_key = (chat_id, user_id)
            previous_violations = self.tracker.get_count(chat_id, user_id)
            self.rejoin_spam_state[burst_key] = {
                "previously_banned": True,
                "previous_violations": previous_violations,
            }
            self.punished_users.discard(punish_key)
            burst_task = self.spam_burst_tasks.pop(burst_key, None)
            if burst_task:
                burst_task.cancel()
            self.spam_burst_users.discard(burst_key)
            self.spam_burst_messages.pop(burst_key, None)


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
                restore_rejoin_spam_state(chat_id, user_id)
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
                punish_key = f"{chat_id}:{user_id}"
                burst_key = (chat_id, user_id)
                history = get_user_history(chat_id, user_id)
                rejoin_state = self.rejoin_spam_state.get(burst_key, {})
                self.logger.log_info(
                    "SPLUS REJOIN STATE DEBUG\n"
                    f"user_id={user_id}\n"
                    f"chat_id={chat_id}\n"
                    f"previously_banned={rejoin_state.get('previously_banned', False)}\n"
                    f"previous_violations={rejoin_state.get('previous_violations', 0)}\n"
                    "new_spam_detected=False\n"
                    "ban_triggered=False\n"
                    f"punish_key={punish_key}\n"
                    f"in_punished_users={punish_key in self.punished_users}\n"
                    f"in_spam_burst_users={burst_key in self.spam_burst_users}\n"
                    f"history_count={len(history) if history is not None else 0}\n"
                    f"spam_count={self.tracker.get_count(chat_id, user_id)}"
                )

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
                        restore_rejoin_spam_state(chat_id, user_id)
                        self.spammer_messages.pop(user_id, None)
                        self.logger.log_info(
                            "Detected manual release, removed user from permanent "
                            f"banned storage. user_id={user_id} "
                            f"removed={removed_count} remaining={remaining_records}"
                        )
                        return

                    self.moderation_queue.enqueue(
                        chat_id,
                        "ban",
                        user_id=user_id,
                        timeout_seconds=20,
                        operation=lambda: self.client.edit_permissions(
                            chat_id,
                            user,
                            until_date=None,
                            view_messages=False,
                        ),
                    )
                    print(f"🚫 queued banned user rejoin block: {user_id}")

            except Exception as e:
                print(f"join ban check error: {e}")


        @self.client.on(events.NewMessage())
        async def new_message_handler(event):
            instrument_event(event, self.logger)
            raw_text = event.message.message or ""
            # کاربر ممکن است «اطلاع‌رسانی» را با نیم‌فاصله (ZWNJ) بنویسد — همان
            # املایی که خودِ ربات در پیام‌هایش به کار می‌برد. مقایسهٔ خام آن را
            # رد می‌کرد و دستور بی‌صدا نادیده گرفته می‌شد.
            text = normalize_command_text(raw_text)
            # BROADCAST TRACE: قبل از هر await ثبت می‌شود تا اگر یکی از
            # فراخوانی‌های بعدی استثنا داد، بدانیم پیام اصلاً رسیده بود.
            _broadcast_words = BROADCAST_COMMAND_WORDS
            if is_broadcast_command(raw_text):
                try:
                    _owner_cfg = get_owner()
                except Exception as _owner_error:
                    _owner_cfg = {"error": repr(_owner_error)}
                self.logger.log_info(
                    "BROADCAST_COMMAND_RECEIVED "
                    f"raw_text={raw_text!r} "
                    f"normalized_text={text!r} "
                    f"event_out={getattr(event, 'out', None)} "
                    f"is_private={getattr(event, 'is_private', None)} "
                    f"event_chat_id={getattr(event, 'chat_id', None)} "
                    f"owner_id_from_config={_owner_cfg} "
                    f"message_id={getattr(event.message, 'id', None)} "
                    f"entity_count={len(getattr(event.message, 'entities', None) or [])}"
                )
            # get_chat() نیازمند resolve شدن peer است و روی session تازه (کش
            # entity خالی) می‌تواند خطا بدهد. چون هیچ try/except بیرونی وجود
            # ندارد، آن خطا کل handler را بی‌صدا از بین می‌برد و دستور کاربر
            # هرگز اجرا نمی‌شود. اینجا خطا مهار می‌شود تا مسیر ادامه یابد.
            routing_chat = None
            try:
                routing_chat = await event.get_chat()
            except Exception as error:
                self.logger.log_error(
                    "BROADCAST ROUTE ENTER get_chat FAILED "
                    f"text={text!r} error={error!r} -> continuing with peer fallback"
                )

            # وقتی get_chat ناموفق است، نوع چت از خودِ peer رویداد استنتاج
            # می‌شود؛ PeerUser یعنی پیوی. این مسیر به کش entity وابسته نیست.
            peer_is_user = isinstance(
                getattr(event, "_chat_peer", None), types.PeerUser
            )
            # آخرین fallback: در سروش پلاس شناسهٔ مثبت یعنی کاربر و شناسهٔ منفی
            # یعنی گروه/کانال. فقط وقتی استفاده می‌شود که chat اصلاً resolve نشده.
            event_chat_id = getattr(event, "chat_id", None)
            positive_chat_id = (
                routing_chat is None
                and isinstance(event_chat_id, int)
                and event_chat_id > 0
            )
            is_private_splus = bool(
                event.is_private
                or routing_chat.__class__.__name__ == "User"
                or peer_is_user
                or positive_chat_id
            )
            if text in _broadcast_words:
                self.logger.log_info(
                    "BROADCAST ROUTE CHAT RESOLVED "
                    f"chat_type={routing_chat.__class__.__name__} "
                    f"chat_id={getattr(routing_chat, 'id', None)} "
                    f"private_route={is_private_splus}"
                )
            is_broadcast_text = text in {"اطلاع رسانی", "تایید", "✅ تایید", "لغو", "❌ لغو"}
            is_name_family_trace_message = (
                text == "اسم فامیل" or len(text.splitlines()) >= 7
            )
            if is_broadcast_text:
                self.logger.log_info(
                    "BROADCAST COMMAND RECEIVED "
                    f"text={text!r} event_out={event.out} "
                    f"event_is_private={event.is_private} "
                    f"chat_type={routing_chat.__class__.__name__} "
                    f"private_route={is_private_splus}"
                )
            if (
                event.out
                and is_private_splus
                and event.message.id in getattr(self, "broadcast_bot_message_ids", set())
            ):
                self.broadcast_bot_message_ids.discard(event.message.id)
                return

            is_mode_command = text in {"فعال", "غیر فعال"}
            mode_username = None
            if is_mode_command:
                sender_for_mode = await event.get_sender()
                sender_username_for_mode = getattr(sender_for_mode, "username", None)
                try:
                    client_me = await self.client.get_me()
                    client_me_id = getattr(client_me, "id", None)
                    client_me_username = getattr(client_me, "username", None)
                except Exception as error:
                    client_me_id = None
                    client_me_username = None
                    self.logger.log_error(f"OWNER RUNTIME TRACE get_me error: {error}")

                normalized_sender = normalize_username(sender_username_for_mode)
                normalized_client = normalize_username(client_me_username)
                global_owner_config = get_owner()
                is_global_owner_sender = is_global_owner(getattr(sender_for_mode, "id", None))
                is_global_owner_client = is_global_owner(client_me_id)
                mode_username = (
                    client_me_username if event.out else sender_username_for_mode
                )
                self.logger.log_info(
                    "OWNER RUNTIME TRACE\n"
                    f"raw_text={raw_text!r}\n"
                    f"event_out={event.out}\n"
                    f"sender_id={getattr(sender_for_mode, 'id', None)}\n"
                    f"sender_username={sender_username_for_mode!r}\n"
                    f"client_me_id={client_me_id}\n"
                    f"client_me_username={client_me_username!r}\n"
                    f"normalized_sender={normalized_sender!r}\n"
                    f"normalized_client={normalized_client!r}\n"
                    f"global_owner_config={global_owner_config!r}\n"
                    f"is_global_owner_sender={is_global_owner_sender}\n"
                    f"is_global_owner_client={is_global_owner_client}"
                )
                is_global_owner_for_mode = (
                    is_global_owner_client if event.out else is_global_owner_sender
                )
                if event.out and not is_global_owner_for_mode:
                    self.logger.log_info("OWNER RUNTIME TRACE STOP: event.out gate")
                    return
            elif event.out:
                if is_private_splus:
                    private_sender = await event.get_sender()
                    if event.out:
                        private_me = await self.client.get_me()
                        private_owner_id = getattr(private_me, "id", None)
                    else:
                        private_owner_id = getattr(private_sender, "id", None)
                    is_broadcast_trigger = text == "اطلاع رسانی"
                    has_broadcast_session = bool(
                        get_broadcast_state(private_owner_id)
                    )
                    if (
                        is_global_owner(private_owner_id)
                        and (is_broadcast_trigger or has_broadcast_session)
                    ):
                        pass
                    # پیام‌های خروجی عادی باید به handler برسند؛ این ربات
                    # userbot است و فرمان مالک نیز event.out=True دارد.
                # پاسخ‌های خود ربات فرمان نیستند و در handler واکنش تازه‌ای
                # تولید نمی‌کنند؛ پاسخ‌های broadcast هم با message id جدا می‌شوند.

            # MASTER GROUP MODE GATE: every incoming group message passes here first.
            if not is_private_splus:
                try:
                    chat_lock = await event.get_chat()
                except Exception as error:
                    chat_lock = routing_chat
                    self.logger.log_error(
                        f"GROUP GATE get_chat FAILED error={error!r}"
                    )
                lock_id = getattr(chat_lock, "id", None)
                try:
                    sender_lock = await event.get_sender()
                except Exception as error:
                    sender_lock = None
                    self.logger.log_error(
                        f"GROUP GATE get_sender FAILED error={error!r}"
                    )
                sender_id = getattr(sender_lock, "id", None)
                if lock_id is None:
                    # چت resolve نشده است؛ is_active(None) همیشه False است و
                    # پیام بی‌صدا دور ریخته می‌شود. این حالت باید دیده شود.
                    self.logger.log_error(
                        "GROUP GATE UNRESOLVED CHAT "
                        f"text={text[:40]!r} event_chat_id={event_chat_id} "
                        f"event_is_private={event.is_private} -> message dropped"
                    )
                group_is_active = is_active(lock_id)
                sender_username = (
                    mode_username if is_mode_command else getattr(
                        sender_lock, "username", None
                    )
                )
                normalized_username = normalize_username(sender_username)
                can_change_group_mode = is_global_owner(sender_id)
                is_enable_command = text == "فعال"
                is_disable_command = text == "غیر فعال"

                if is_enable_command or is_disable_command:
                    self.logger.log_info(
                        "GROUP MODE DEBUG "
                        f"chat_id={lock_id} sender_id={sender_id} "
                        f"sender_username={sender_username!r} "
                        f"normalized_username={normalized_username!r} "
                        f"text={text!r} disabled_before={not group_is_active} "
                        f"global_owner_check={can_change_group_mode} "
                        f"mode_owner_check={can_change_group_mode} "
                        f"enable_match={is_enable_command} "
                        f"disable_match={is_disable_command}"
                    )

                if not group_is_active:
                    if is_name_family_trace_message:
                        self.logger.log_info(
                            "NAME FAMILY TRACE CORE_BLOCK "
                            f"reason=group_inactive chat_id={lock_id} "
                            f"message_id={getattr(event.message, 'id', None)}"
                        )
                    if is_enable_command and can_change_group_mode:
                        title = getattr(chat_lock, "title", "")
                        activate_group(lock_id, title)
                        await send_activation_message(
                            self, event, lock_id, title
                        )
                        return
                    # ⏳ گروهی که با پایان مهلت بسته شده باید بتواند دوباره
                    # باز شود. بدون این استثنا، سه دستور انقضا هرگز به
                    # هندلر نمی‌رسیدند و گروه برای همیشه قفل می‌ماند.
                    if (
                        expiry_command(text) is not None
                        and can_change_group_mode
                    ):
                        self.logger.log_info(
                            "GROUP EXPIRY REACTIVATION ALLOWED "
                            f"chat_id={lock_id} sender_id={sender_id} "
                            f"command={text!r}"
                        )
                        title = getattr(chat_lock, "title", "")
                        activate_group(lock_id, title)
                    else:
                        return

                if is_disable_command:
                    if can_change_group_mode:
                        title = getattr(chat_lock, "title", "")
                        deactivate_group(lock_id, title)
                        for task in self.group_timer_tasks.pop(lock_id, set()):
                            task.cancel()
                        # اسم فامیل صف تایمر مستقل خودش را دارد و باید
                        # جداگانه و تمیز بسته شود.
                        cancel_name_family_round(lock_id)
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                        )
                    return

            # آزاد کردن کاربر محروم شده
            if not is_private_splus and text == "آزاد":
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

                    async def unban_succeeded(_result):
                        self.tracker.banned_users.pop(
                            f"{event.chat_id}:{user.id}", None
                        )
                        restore_rejoin_spam_state(event.chat_id, user.id)
                        self.spammer_messages.pop(user.id, None)
                        self.logger.log_info(
                            f"UNBAN COMPLETE user_id={user.id} removed successfully"
                        )
                        await event.reply("♻️ کاربر آزاد شد")

                    async def unban_failed(_error):
                        await event.reply("❌ آزاد کردن انجام نشد")

                    self.moderation_queue.enqueue(
                        event.chat_id,
                        "unban",
                        user_id=user.id,
                        timeout_seconds=20,
                        operation=lambda: self.admin_actions.unban_user(
                            event.chat_id, user.id, getattr(user, "username", None)
                        ),
                        on_success=unban_succeeded,
                        on_failure=unban_failed,
                    )

                except Exception as e:
                    await event.reply(f"❌ خطا در آزاد کردن: {e}")
                return



              # پیوی فقط دستور صفر کردن تخلف
            if is_private_splus:
                text = (event.message.message or "").strip()
                _is_broadcast_word = text in _broadcast_words
                if _is_broadcast_word:
                    self.logger.log_info(
                        f"BROADCAST ROUTE PRIVATE BRANCH text={text!r}"
                    )
                try:
                    sender = await event.get_sender()
                except Exception as error:
                    self.logger.log_error(
                        f"BROADCAST OWNER CHECK get_sender FAILED error={error!r}"
                    )
                    raise
                if event.out:
                    try:
                        private_me = await self.client.get_me()
                    except Exception as error:
                        self.logger.log_error(
                            f"BROADCAST OWNER CHECK get_me FAILED error={error!r}"
                        )
                        raise
                    sender_id = getattr(private_me, "id", None)
                else:
                    sender_id = getattr(sender, "id", None)

                _owner_ok = is_global_owner(sender_id)
                if _is_broadcast_word or _owner_ok:
                    self.logger.log_info(
                        "BROADCAST OWNER CHECK "
                        f"sender_id={sender_id} "
                        f"sender_username={getattr(sender, 'username', None)!r} "
                        f"event_out={event.out} "
                        f"configured_owner={get_owner()!r} "
                        f"is_global_owner={_owner_ok}"
                    )
                if not _owner_ok and _is_broadcast_word:
                    self.logger.log_info(
                        "BROADCAST ROUTE STOP reason=not_global_owner "
                        f"sender_id={sender_id}"
                    )

                if _owner_ok:
                    self.logger.log_info(
                        "BROADCAST COMMAND RECEIVED "
                        f"owner_id={sender_id} text={text!r} event_out={event.out}"
                    )
                    if await handle_private_broadcast(self, event, sender_id, text):
                        self.logger.log_info(
                            f"BROADCAST ROUTE HANDLED text={text!r}"
                        )
                        return
                    if _is_broadcast_word:
                        self.logger.log_info(
                            "BROADCAST ROUTE NOT HANDLED "
                            f"text={text!r} (handler returned False)"
                        )

                if "صفر" in text:
                    sender = await event.get_sender()
                    if not is_global_owner(getattr(sender, "id", None)):
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

                # 💰 اقتصاد در پیوی هم باید کار کند.
                #
                # این شاخه با یک return بی‌قیدوشرط تمام می‌شود، پس هر پیام
                # خصوصی پیش از رسیدن به handler دور ریخته می‌شد و «موجودی»
                # و «فروشگاه» در پیوی هیچ واکنشی نداشتند. مسیر اقتصاد
                # صراحتاً پیش از آن return فراخوانی می‌شود.
                try:
                    private_sender = await event.get_sender()
                    private_user_id = getattr(private_sender, "id", None)
                    if private_user_id is not None and await handle_economy(
                        self, event, private_user_id, private_user_id,
                        private_sender, text, self.logger,
                    ):
                        return
                except Exception as error:
                    self.logger.log_error(
                        "ECONOMY PRIVATE ROUTE FAILED "
                        f"text={text!r} error={error!r}"
                    )

                # پیام خصوصی پس از route اختصاصی هرگز وارد handler گروهی نمی‌شود.
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

            started = time.perf_counter()
            if is_name_family_trace_message:
                self.logger.log_info(
                    "NAME FAMILY TRACE CORE_DISPATCH "
                    f"chat_id={event.chat_id} message_id={getattr(event.message, 'id', None)} "
                    f"line_count={len(text.splitlines())}"
                )
            await handle_new_message(self, event)
            elapsed = time.perf_counter() - started
            if elapsed >= 0.05:
                self.logger.log_info(
                    "MESSAGE PROCESS TIME "
                    f"receive={started:.6f} total={elapsed:.4f}s "
                    f"chat_id={event.chat_id} text={text!r}"
                )


        reconnect_delay = 1
        while True:
            try:
                print("✅ ربات فعال شد و منتظر پیام است")
                await self.client.run_until_disconnected()
                raise ConnectionError("SPlusthon connection closed")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.logger.log_error(
                    "SPLUS RECONNECT "
                    f"reason={error!r} retry_in={reconnect_delay}s"
                )
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)
                try:
                    await self.client.connect()
                    self.bot_account_id = getattr(
                        await self.client.get_me(), "id", self.bot_account_id
                    )
                    reconnect_delay = 1
                    self.logger.log_info("SPLUS RECONNECT SUCCESS")
                except asyncio.CancelledError:
                    raise
                except Exception as reconnect_error:
                    self.logger.log_error(
                        f"SPLUS RECONNECT FAILED: {reconnect_error!r}"
                    )


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




