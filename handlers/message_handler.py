import asyncio as _asyncio
from collections import deque

from modules.fill_blank import check_fill
from modules.riddles import check_answer
from modules.group_stats import add_message
from modules.group_storage import activate_group, deactivate_group
from modules.owner_check import is_global_owner
from modules.spam_history import save_history_message
from modules.spam_history import is_repeat
from modules.fill_blank import new_fill, get_fill_answer
from modules.riddles import new_riddle, get_answer
from modules.multiple_choice import (
    start_question,
    answer_question,
    get_active_question,
    clear_question,
)
from modules.user_original_storage import (
    begin_registration,
    is_waiting_for_original,
    save_original,
    get_original,
)
from modules.jokes import get_joke
from modules.simple_replies import SIMPLE_REPLIES, INSULTS, INSULT_REPLY
from modules.group_stats import add_kick, add_mute, make_report, add_deleted_count
from modules.spam_history import get_message_ids, clear_user
from modules.web_search import can_search, search_web
from modules.jorat_haghighat import get_jorat, get_haghighat
from modules.font_converter import make_fonts
from modules.admin_storage import add_admin, remove_admin, is_admin
from modules.banned_storage import add_banned
from modules.group_storage import set_group_owner, get_group_owner, remove_group_owner
from handlers.admin_handler import handle_admin_commands
from splusthon.tl.types import MessageEntityBold, MessageEntityBlockquote
from splusthon.tl import functions
from splusthon import types


def _format_group_member(user):
    username = getattr(user, "username", None)
    if username:
        return f"@{username}"

    user_id = getattr(user, "id", None)
    name = " ".join(
        part.strip(" |")
        for part in (
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        )
        if part and part.strip(" |")
    )

    if name:
        return name
    if user_id is not None:
        return f"ID: {user_id}"
    return "کاربر ناشناس"


def _format_banned_user(user, user_id):
    username = getattr(user, "username", None) if user else None
    if username:
        return f"@{username}"

    display_name = " ".join(
        part for part in (
            getattr(user, "first_name", None) if user else None,
            getattr(user, "last_name", None) if user else None,
        ) if part
    ).strip()
    return display_name or str(user_id)


async def _send_moderation_notification_once(
    bot, chat_id, user_id, action, source_message_id, text
):
    key = (chat_id, user_id, action, source_message_id)
    if not hasattr(bot, "moderation_notification_guard"):
        bot.moderation_notification_guard = set()
        bot.moderation_notification_order = deque(maxlen=1000)
    if key in bot.moderation_notification_guard:
        return False

    if len(bot.moderation_notification_order) == bot.moderation_notification_order.maxlen:
        expired_key = bot.moderation_notification_order.popleft()
        bot.moderation_notification_guard.discard(expired_key)
    bot.moderation_notification_guard.add(key)
    bot.moderation_notification_order.append(key)
    try:
        await bot.client.send_message(chat_id, text)
        return True
    except Exception:
        bot.moderation_notification_guard.discard(key)
        raise


def _track_group_timer(bot, chat_id, task):
    if not hasattr(bot, "group_timer_tasks"):
        bot.group_timer_tasks = {}
    tasks = bot.group_timer_tasks.setdefault(chat_id, set())
    tasks.add(task)

    def discard_finished_task(completed_task):
        tasks.discard(completed_task)
        if not tasks:
            bot.group_timer_tasks.pop(chat_id, None)

    task.add_done_callback(discard_finished_task)
    return task


def _queue_spam_burst_deletion(bot, chat_id, user_id, message_ids):
    key = (chat_id, user_id)
    bot.spam_burst_messages.setdefault(key, set()).update(message_ids)
    existing_task = bot.spam_burst_tasks.get(key)
    if existing_task and not existing_task.done():
        return

    async def delete_burst_messages():
        idle_rounds = 0
        try:
            while idle_rounds < 3:
                ids = sorted(bot.spam_burst_messages.pop(key, set()))
                if not ids:
                    idle_rounds += 1
                    await _asyncio.sleep(0.2)
                    continue

                idle_rounds = 0
                for start in range(0, len(ids), 100):
                    batch = ids[start:start + 100]
                    try:
                        await bot.client.delete_messages(chat_id, batch)
                    except Exception as error:
                        bot.logger.log_error(
                            f"خطا در حذف دسته‌ای spam burst {user_id}: {error}"
                        )
                    await _asyncio.sleep(0.2)
        finally:
            bot.spam_burst_tasks.pop(key, None)

    bot.spam_burst_tasks[key] = _asyncio.create_task(delete_burst_messages())


async def get_activation_admin_info(bot, chat_id):
    owner = None
    admins = []
    admin_ids = set()

    def collect_participants(users, participants):
        nonlocal owner
        users = {
            getattr(user, "id", None): user
            for user in users
        }

        for participant in participants:
            user_id = getattr(participant, "user_id", None)
            user = users.get(user_id)
            if not user:
                continue

            participant_type = participant.__class__.__name__
            if "Creator" in participant_type:
                owner = _format_group_member(user)
            elif "Admin" in participant_type and user_id not in admin_ids:
                admin_ids.add(user_id)
                admins.append(_format_group_member(user))

    try:
        channel = await bot.client.get_input_entity(chat_id)
        offset = 0
        limit = 100

        while True:
            result = await bot.client(
                functions.channels.GetParticipantsRequest(
                    channel=channel,
                    filter=types.ChannelParticipantsAdmins(),
                    offset=offset,
                    limit=limit,
                    hash=0,
                )
            )
            users = getattr(result, "users", [])
            if not users:
                break

            collect_participants(
                users,
                getattr(result, "participants", []),
            )
            if len(users) < limit:
                break
            offset += len(users)

    except Exception as channel_error:
        # Basic groups do not support channels.GetParticipantsRequest.
        try:
            result = await bot.client(
                functions.messages.GetFullChatRequest(chat_id=chat_id)
            )
            participant_container = getattr(
                getattr(result, "full_chat", None),
                "participants",
                None,
            )
            collect_participants(
                getattr(result, "users", []),
                getattr(participant_container, "participants", []),
            )
        except Exception as basic_chat_error:
            bot.logger.log_error(
                "خطا در دریافت مالک و ادمین‌های گروه "
                f"{chat_id}: channel={channel_error}; basic_chat={basic_chat_error}"
            )

    return owner, admins


async def send_activation_message(bot, event, chat_id, title):
    owner, admins = await get_activation_admin_info(bot, chat_id)
    owner_text = owner or "یافت نشد (دسترسی کافی ندارم)"
    admins_text = (
        "\n".join(
            f"{index}. {admin}"
            for index, admin in enumerate(admins, 1)
        )
        if admins else "ندارد"
    )

    owner_section = f"👑 مالک گروه:\n{owner_text}"
    admins_section = f"👮 ادمین های گروه:\n{admins_text}"
    activation_hint = (
        "برای آشنایی بیشتر کلمه راهنما را ارسال کنید یا بیو ربات، "
        "کانال راهنما را مطالعه کنید."
    )
    activation_text = (
        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\n\n"
        f"{owner_section}\n\n{admins_section}\n\n{activation_hint}"
    )

    def u16_length(value):
        return len(value.encode("utf-16-le")) // 2

    owner_offset = activation_text.index(owner_section)
    admins_offset = activation_text.index(admins_section)
    hint_offset = activation_text.index(activation_hint)
    entities = [
        MessageEntityBlockquote(
            offset=u16_length(activation_text[:owner_offset]),
            length=u16_length(owner_section),
        ),
        MessageEntityBold(
            offset=u16_length(activation_text[:owner_offset]),
            length=u16_length("👑 مالک گروه:"),
        ),
        MessageEntityBlockquote(
            offset=u16_length(activation_text[:admins_offset]),
            length=u16_length(admins_section),
        ),
        MessageEntityBold(
            offset=u16_length(activation_text[:admins_offset]),
            length=u16_length("👮 ادمین های گروه:"),
        ),
        MessageEntityBold(
            offset=u16_length(activation_text[:hint_offset]),
            length=u16_length(activation_hint),
        ),
    ]
    await event.respond(activation_text, formatting_entities=entities)


def _can_manage_group_admins(bot, chat_id, user_id, username):
    if is_global_owner(username):
        return True

    group_owner_id = get_group_owner(chat_id)
    return group_owner_id is not None and str(user_id) == str(group_owner_id)


DELETE_COMMAND_COOLDOWNS = {}


def _has_group_management_permission(bot, chat_id, user_id, username):
    return (
        _can_manage_group_admins(bot, chat_id, user_id, username)
        or is_admin(chat_id, username)
        or bot.config_manager.is_admin(user_id, username)
    )


def _can_delete_messages(bot, chat_id, user_id, username):
    return _has_group_management_permission(
        bot, chat_id, user_id, username
    )


async def handle_new_message(bot, event):
    """هندلر اصلی برای پیام‌های جدید"""
    try:
        # اگر پیام متنی نیست رد کن (مثلا سرویس)
        if not event.message or not hasattr(event.message, 'message'):
            return

        # اطلاعات پیام
        message_text = getattr(event.message, "message", "") or ""
        # برای کپشن عکس/فایل هم چک کن
        if not message_text and hasattr(
                event.message, 'file') and event.message.file:
            # اگر فایل دارد، نام فایل یا کپشن را چک کن
            try:
                caption = getattr(event.message, 'caption', None) or ""
                message_text = caption
            except BaseException:
                pass

        if not message_text:
            return



        chat_id = event.chat_id
        sender = await event.get_sender()
        user_id = sender.id if sender else 0

        clean_text = message_text.strip()
        burst_key = (chat_id, user_id)
        if burst_key in bot.spam_burst_users:
            _queue_spam_burst_deletion(
                bot, chat_id, user_id, {event.message.id}
            )
            return

        if clean_text == "صفر":
            if not is_global_owner(getattr(sender, "username", None)):
                await event.reply("❌ فقط مالک اصلی ربات اجازه استفاده از این دستور را دارد")
                return
            if not event.reply_to:
                await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                return

            try:
                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id,
                )
                target_user = await reply_msg.get_sender() if reply_msg else None
                if not target_user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                bot.tracker.reset_count(chat_id, target_user.id)
                await event.reply("✅ تخلفات کاربر صفر شد.")
            except Exception as e:
                bot.logger.log_error(f"خطا در صفر کردن تخلفات: {e}")
                await event.reply(f"❌ خطا: {e}")
            return

        if clean_text == "ثبت اصل":
            begin_registration(user_id)
            await event.reply("لقب یا اصل خودتو بنویس")
            return

        if is_waiting_for_original(user_id):
            save_original(user_id, clean_text)
            await event.reply("✅ اصل شما ثبت شد")
            return

        if clean_text == "اصلم":
            original = get_original(user_id)
            if original:
                await event.reply(f"اصل شما:\n\n{original}")
            else:
                await event.reply(
                    "هنوز اصلی ثبت نکردی. برای ثبت بنویس: ثبت اصل"
                )
            return

        owner_chat_id = chat_id
        if not event.is_private and clean_text == "سلام":
            owner_chat = await event.get_chat()
            owner_chat_id = getattr(owner_chat, "id", chat_id)
        registered_owner_id = get_group_owner(owner_chat_id)
        if (
            not event.is_private
            and registered_owner_id is not None
            and clean_text == "سلام"
            and str(user_id) == str(registered_owner_id)
        ):
            await event.reply("سلام مالک جون 👑")
            return

        if clean_text in INSULTS:
            await event.reply(INSULT_REPLY)
            return

        simple_reply = SIMPLE_REPLIES.get(clean_text)
        if simple_reply:
            await event.reply(simple_reply)
            return

        # ضدتکرار فقط برای پیام‌های سریع و یکسانِ کاربران عادی اجرا می‌شود.
        sender_username = getattr(sender, "username", None)
        is_group_moderator = (
            not event.is_private
            and _has_group_management_permission(
                bot, chat_id, user_id, sender_username
            )
        )
        if not is_group_moderator:
            try:
                save_history_message(chat_id, user_id, event.message.id, message_text)
                if is_repeat(chat_id, user_id, message_text):
                    punish_key = f"{chat_id}:{user_id}"
                    if punish_key in bot.punished_users:
                        return
                    bot.punished_users.add(punish_key)
                    bot.spam_burst_users.add(punish_key)
                    ids = get_message_ids(chat_id, user_id)
                    banned = await bot.admin_actions.ban_user(
                        chat_id, user_id, reason="اسپم تکراری"
                    )
                    if banned:
                        _queue_spam_burst_deletion(
                            bot, chat_id, user_id, set(ids)
                        )
                        await _send_moderation_notification_once(
                            bot, chat_id, user_id, "spam_ban", event.message.id,
                            "🚫 کاربر "
                            f"{_format_banned_user(sender, user_id)} "
                            "به دلیل اسپم مکرر از گروه اخراج شد.",
                        )
                        clear_user(chat_id, user_id)
                    else:
                        bot.punished_users.discard(punish_key)
                        bot.spam_burst_users.discard(punish_key)
                    return
            except Exception as e:
                print("history error:", e)

        # جستجوی وب
        if clean_text.startswith("جستجو "):
            query = clean_text.replace("جستجو ", "", 1).strip()

            # فیلتر مطالب غیرمجاز جستجو
            blocked_search_words = [
    "porn",
    "porno",
    "xxx",
    "sex",
    "s e x",
    "سکس",
    "سکسی",
    "پورن",
    "فیلم پورن",
    "فیلم سوپر",
    "سوپر",
    "gay",
    "گی",
    "lez",
    "les",
    "لز",
    "تریسام",
    "threesome",
    "adult",
    "nude",
    "naked",
    "برهنه",
    "18+",
    "18",
    "erotic",
    "شهوت",
    "شهوانی"
]

            if any(word.lower() in query.lower() for word in blocked_search_words):
                await event.reply("🚫 جستجو این مطلب غیرمجاز است.")
                return

            if query:
                ok, wait = can_search(user_id)
                if not ok:
                    await event.reply(f"⏳ لطفاً {wait} ثانیه صبر کنید")
                    return

                result = search_web(query)
                await event.reply(result)
                return


        # بازی چهار گزینه‌ای
        normalized_game_command = " ".join(
            clean_text.replace("‌", " ").split()
        )
        if normalized_game_command == "چهار گزینه ای":
            try:
                quiz = start_question(chat_id)
                options_text = "\n".join(
                    f"{index}) {option}"
                    for index, option in enumerate(quiz["options"], 1)
                )
                quiz_text = (
                    "🎯 سوال چهار گزینه‌ای:\n\n"
                    f"{quiz['question']}\n\n"
                    f"{options_text}"
                )

                def u16_length(value):
                    return len(value.encode("utf-16-le")) // 2

                option_start = quiz_text.index(options_text)
                entities = []
                current_offset = option_start
                for option_line in options_text.split("\n"):
                    entities.append(
                        MessageEntityBold(
                            offset=u16_length(quiz_text[:current_offset]),
                            length=u16_length(option_line),
                        )
                    )
                    current_offset += len(option_line) + 1

                await event.reply(quiz_text, formatting_entities=entities)

                async def multiple_choice_timer():
                    import asyncio
                    await asyncio.sleep(30)
                    active_quiz = get_active_question(chat_id)
                    if active_quiz and active_quiz["token"] == quiz["token"]:
                        clear_question(chat_id, quiz["token"])
                        await event.reply(
                            "⏰ زمان تمام شد!\n\n"
                            f"پاسخ درست:\nگزینه {active_quiz['answer']}"
                        )

                import asyncio
                _track_group_timer(
                    bot,
                    chat_id,
                    _asyncio.create_task(multiple_choice_timer()),
                )

            except Exception as e:
                bot.logger.log_error(f"خطای بازی چهار گزینه‌ای: {e}")
            return

        # بازی جای خالی
        if clean_text == "جای خالی":
            try:
                q = new_fill(chat_id, user_id)
                await event.reply("📝 جای خالی:\n\n" + q + "\n\n⏳ ۳۰ ثانیه فرصت داری")

                async def fill_timer():
                    import asyncio
                    await asyncio.sleep(30)
                    ans = get_fill_answer(chat_id, user_id)
                    if ans:
                        await event.reply(f"⏰ زمان تمام شد!\n✅ پاسخ: {ans}")

                _track_group_timer(
                    bot,
                    chat_id,
                    _asyncio.create_task(fill_timer()),
                )

            except Exception as e:
                bot.logger.log_error(f"خطای جای خالی: {e}")
            return

        # RIDDLE_SAFE_INSERTED
        if clean_text == "چیستان":
            try:
                q = new_riddle(chat_id, user_id)
                await event.reply("🧩 چیستان:\n\n" + q + "\n\n⏳ ۵۰ ثانیه فرصت داری جواب بده")

                async def riddle_timer():
                    import asyncio
                    await asyncio.sleep(60)
                    answer = get_answer(chat_id, user_id)
                    if answer:
                        await event.reply(f"⏰ زمان چیستان تمام شد!\n✅ پاسخ: {answer}")

                _track_group_timer(
                    bot,
                    chat_id,
                    _asyncio.create_task(riddle_timer()),
                )

            except Exception as e:
                bot.logger.log_error(f"خطای چیستان: {e}")
            return


        # بررسی جواب جای خالی
        try:
            if check_fill(chat_id, user_id, clean_text):
                await event.reply("🎉 آفرین! درست بود\n⭐ امتیاز گرفتی")
                return
        except Exception as e:
            bot.logger.log_error(f"خطای جای خالی: {e}")

        try:
            if check_answer(chat_id, user_id, clean_text):
                await event.reply("🎉 آفرین! پاسخ درست بود ✅")
                return
        except Exception as e:
            bot.logger.log_error(f"خطای بررسی جواب چیستان: {e}")

        try:
            result = answer_question(chat_id, clean_text)
            if result is not None:
                is_correct, correct_option = result
                if is_correct:
                    await event.reply("✅ آفرین! پاسخ درست بود 🎉")
                else:
                    await event.reply(
                        f"❌ غلط بود. گزینه {correct_option} درست بود."
                    )
                return
        except Exception as e:
            bot.logger.log_error(f"خطای بررسی پاسخ چهار گزینه‌ای: {e}")

# ثبت آمار پیام گروه
        try:
            if not event.is_private:
                sender_stats = await event.get_sender()
                chat_stats = await event.get_chat()

                add_message(
                    getattr(chat_stats, "id", 0),
                    getattr(sender_stats, "id", 0),
                    getattr(sender_stats, "username", "") or ""
                )

        except Exception as e:
            bot.logger.log_error(
                f"خطای ثبت آمار پیام: {e}"
            )

        # اتصال دستورات فیلتر کلمات گروه
        try:
            sender = await event.get_sender()
            user_id = getattr(sender, "id", 0)

            chat = await event.get_chat()
            chat_id = getattr(chat, "id", 0)

            if await bot.check_group_word_commands(
                event,
                clean_text,
                chat_id,
                user_id
            ):
                return

        except Exception as e:
            bot.logger.log_error(
                f"خطای فیلتر گروه: {e}"
            )

        # بازی جرعت حقیقت
        clean_text = message_text.strip()

        if clean_text in ["جرعت", "جرات", "جرئت"]:
            await event.reply("🎯 جرعت:\n" + get_jorat())
            return

        if clean_text in ["حقیقت", "حقیقت بگو"]:
            await event.reply("🧠 حقیقت:\n" + get_haghighat())
            return



        # فونت ساز چند مدلی
        if clean_text.startswith("فونت "):
            font_text = clean_text.replace("فونت ", "", 1).strip()

            if font_text:
                try:
                    result = make_fonts(font_text)

                    if isinstance(result, list):
                        result = "\n\n".join(result)

                    await event.reply(
                        "✨ فونت‌های ساخته شده:\n\n" + str(result)
                    )

                except Exception as e:
                    bot.logger.log_error(
                        f"خطای فونت ساز: {e}"
                    )

            return


        # جک
        if clean_text == "جک":
            await event.reply(get_joke())
            return

        # پاسخ معرفی ربات
        if clean_text.strip() in ["ربات", "روباه"]:
            await event.reply(
                "🦊 سلام، من روباه هستم 🤖\n\n"
                "برای آشنایی با امکانات و خدمات بیشتر، کلمه «راهنما» را ارسال کنید."
            )
            return


        if clean_text == "ریست آمار":
            try:
                from modules.group_stats import load_stats, save_stats

                data = load_stats()
                gid = str(chat_id)

                if gid in data:
                    old_members = data[gid].get("members", 0)

                    data[gid]["messages"] = 0
                    data[gid]["deleted"] = 0
                    data[gid]["kicked"] = 0
                    data[gid]["muted"] = 0
                    data[gid]["users"] = {}
                    data[gid]["members"] = old_members

                    save_stats(data)

                await event.reply("✅ آمار گروه ریست شد\n👥 تعداد اعضا حفظ شد")
            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return

        # آمار گروه
        if clean_text in ["آمار گپ", "آمار گروه"]:
            member_count = 0

            try:
                entity = await bot.client.get_input_entity(chat_id)
                full = await bot.client(
                    functions.channels.GetFullChannelRequest(entity)
                )
                member_count = full.full_chat.participants_count
            except Exception as e:
                print("MEMBER COUNT ERROR:", repr(e))
                member_count = 0

            print("FINAL MEMBER COUNT:", member_count)
            await event.reply(make_report(chat_id, member_count))
            return

        # لیست بازی
        if clean_text.strip() in ["لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها"]:
            games_text = (
                "🎮 لیست بازی ها:\n\n"
                "🧩 چیستان\n"
                "یک چیستان با زمان کم دریافت کنید\n\n"
                "🎯 جرعت - حقیقت\n"
                "یک سوال جرعت یا حقیقت تصادفی\n\n"
                "😂 جک\n"
                "یک جک خنده دار دریافت کنید\n\n"
                "✍️ جای خالی\n"
                "۳۰ ثانیه فرصت دارید جای خالی را کامل کنید\n\n"
                "🎯 چهار گزینه‌ای\n"
                "به سؤال پاسخ دهید: 1، 2، 3 یا 4"
            )

            entities = []

            def u16(x):
                return len(x.encode("utf-16-le")) // 2

            for word in [
                "🎮 لیست بازی ها:",
        "🎵 جستجوی آهنگ و مطالب:",
        "جستجو دانلود اسم آهنگ\n"
                    "برای جستجو مطالب بنویسید:\n"
                    "جستجو اسم مطلبی که می‌خواهید بدانید",
                "🧩 چیستان",
                "🎯 جرعت - حقیقت",
                "😂 جک",
                "✍️ جای خالی",
                "🎯 چهار گزینه‌ای"
            ]:
                pos = games_text.find(word)
                if pos != -1:
                    entities.append(
                        MessageEntityBold(
                            offset=u16(games_text[:pos]),
                            length=u16(word)
                        )
                    )

            await event.reply(
                games_text,
                formatting_entities=entities
            )
            return

        # راهنمای ربات
        if clean_text.strip() in ["راهنما", "/help", "!help", "help"]:
            help_text = (
                "📌 راهنمای روباه\n\n"

                "👤 کاربران:\n\n"
                "برای ثبت اصل بنویسید:\n"
                "ثبت اصل\n\n"
                "برای نمایش اصل بنویسید:\n"
                "اصلم\n\n"
                "🎮 لیست بازی ها:\n"
                "برای مشاهده بازی‌ها بنویسید:\n"
                "لیست بازی\n\n"
                "🎵 جستجوی آهنگ و مطالب:\n"
                "برای جستجو بنویسید:\n"
                "جستجو دانلود اسم آهنگ\n\n"
                "برای جستجو مطالب بنویسید:\n"
                "جستجو اسم مطلبی که می‌خواهید بدانید\n\n"
                "✍️ ساخت فونت:\n"
                "فونت متن شما\n\n"

                "🛡️ امنیت گروه:\n"
                "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\n\n"

                "👑 دستورات ادمین‌ها:\n\n"
                "⚠️ اخطار دادن به کاربر:\n"
                "روی پیام ریپلای کنید و بنویسید:\n"
                "اخطار\n\n"
                "🔤 فیلتر کلمات گروه:\n"
                "/فیلتر کلمه  ← افزودن کلمه ممنوعه\n"
                "/رفع کلمه  ← حذف کلمه از فیلتر\n"
                "/فیلترها  ← نمایش لیست فیلترهای گروه\n\n"
                "📊 آمار گروه\n"
                "نمایش آمار پیام‌ها، تعداد اعضا و کاربران فعال گروه\n\n"
                "♻️ ریست آمار\n"
                "صفر کردن آمار گروه (تعداد اعضا باقی می‌ماند)\n\n"
                "✏️ تغییر اسم گروه:\n"
                "!اسم نام جدید گروه\n\n"
                "👑 مدیریت ادمین‌ها:\n\n"
                "➕ افزودن ادمین:\n\n"
                "مالک گروه روی پیام کاربر ریپلای کند و بنویسد:\n"
                "ثبت ادمین\n\n"
                "برای برکناری ادمین بنویسید:\n\n"
                "برای برکناری ادمین:\n"
                "مالک گروه روی پیام ادمین ریپلای کند و بنویسد:\n\n"
                "برکناری ادمین\n\n"
                "یا\n\n"
                "لغو ادمین\n\n"
                "🛡️ حالت سختگیرانه:\n\n"
                "فعال سازی:\n"
                "فعال کلمات ممنوعه\n\n"
                "غیرفعال سازی:\n"
                "لغو کلمات ممنوعه\n\n"
                "🗑️ حذف پیام:\n"
                "حذف یک پیام با ریپلای:\n"
                "پاک\n\n"
                "حذف چند پیام آخر گروه:\n\n"
                "پاک + عدد مورد نیاز\n\n"
                "مثال:\n"
                "پاک 10\n"
                "پاک 100\n"
                "پاک 700\n\n"
                "🔇 سکوت کاربر:\n"
                "روی پیام ریپلای کنید و بنویسید:\n"
                "سکوت\n\n"
                "🔊 رفع سکوت کاربر:\n"
                "روی پیام ریپلای کنید و بنویسید:\n"
                "رفع سکوت\n\n"
                "🚪 اخراج کاربر:\n"
                "روی پیام ریپلای کنید و بنویسید:\n"
                "اخراج\n\n"
                "♻️ آزاد کردن کاربر:\n"
                "برای آزاد کردن کاربر محروم شده بنویسید:\n"
                "آزاد\n\n"
                "⚠️ صفر کردن تخلفات:\n"
                "با سازنده ربات تماس بگیرید:\n"
                "@osine1"
            )

            entities = []

            def u16(x):
                return len(x.encode("utf-16-le")) // 2

            # بولد کردن عنوان چیستان
            try:
                idx = help_text.find("🧩 چیستان")
                if idx >= 0:
                    entities.append(
                        MessageEntityBold(
                            offset=u16(idx),
                            length=u16(len("🧩 چیستان"))
                        )
                    )
            except Exception:
                pass

            for word in [
                    "🧩 چیستان",
                    "🎯 جرعت - حقیقت",
                    "😂 جک:",
                    "✍️ جای خالی",
                  "🧩 چیستان:",
                    "برای ثبت اصل بنویسید:",
                    "برای نمایش اصل بنویسید:",
                  "😂 جک:",
                  "🎯 بازی جرعت حقیقت:",
                  "✍️ ساخت فونت:",
                  "🛡️ امنیت گروه:",
                  "👑 دستورات ادمین‌ها:",
                  "🎮 لیست بازی ها:",
                  "👑 مدیریت ادمین‌ها:",
                  "➕ افزودن ادمین:",
                  "برای برکناری ادمین بنویسید:",
                  "🛡️ حالت سختگیرانه:",
                  "فعال سازی:",
                  "غیرفعال سازی:",
                  "🔤 فیلتر کلمات گروه:",
                  "📊 آمار گروه",
                  "♻️ ریست آمار",
                  "✏️ تغییر اسم گروه:",
                  "🗑️ حذف پیام:",
                  "حذف یک پیام با ریپلای:",
                  "حذف چند پیام آخر گروه:",
                  "🔇 سکوت کاربر:",
                  "🔊 رفع سکوت کاربر:",
                  "🚪 اخراج کاربر:",
                  "♻️ آزاد کردن کاربر:",
        "🔎 جستجو و دانلود آهنگ:",
        "جستجو دانلود اسم آهنگ",
        "برای جستجو مطالب بنویسید:"
              ]:
                pos = help_text.find(word)
                if pos != -1:
                    entities.append(
                        MessageEntityBold(
                            offset=u16(help_text[:pos]),
                            length=u16(word)
                        )
                    )

            quote_sections = [
                "⚠️ اخطار دادن به کاربر:\nروی پیام ریپلای کنید و بنویسید:\nاخطار",
                "🔤 فیلتر کلمات گروه:\n/فیلتر کلمه  ← افزودن کلمه ممنوعه\n/رفع کلمه  ← حذف کلمه از فیلتر\n/فیلترها  ← نمایش لیست فیلترهای گروه",
                "📊 آمار گروه\nنمایش آمار پیام‌ها، تعداد اعضا و کاربران فعال گروه",
                "♻️ ریست آمار\nصفر کردن آمار گروه (تعداد اعضا باقی می‌ماند)",
                "✏️ تغییر اسم گروه:\n!اسم نام جدید گروه",
                "👑 مدیریت ادمین‌ها:\n\n➕ افزودن ادمین:\n\nمالک گروه روی پیام کاربر ریپلای کند و بنویسد:\nثبت ادمین\n\nبرای برکناری ادمین بنویسید:\n\nبرای برکناری ادمین:\nمالک گروه روی پیام ادمین ریپلای کند و بنویسد:\n\nبرکناری ادمین\n\nیا\n\nلغو ادمین",
                "🛡️ حالت سختگیرانه:\n\nفعال سازی:\nفعال کلمات ممنوعه\n\nغیرفعال سازی:\nلغو کلمات ممنوعه",
                "🗑️ حذف پیام:\nحذف یک پیام با ریپلای:\nپاک\n\nحذف چند پیام آخر گروه:\n\nپاک + عدد مورد نیاز\n\nمثال:\nپاک 10\nپاک 100\nپاک 700",
                "🔇 سکوت کاربر:\nروی پیام ریپلای کنید و بنویسید:\nسکوت",
                "🔊 رفع سکوت کاربر:\nروی پیام ریپلای کنید و بنویسید:\nرفع سکوت",
                "🚪 اخراج کاربر:\nروی پیام ریپلای کنید و بنویسید:\nاخراج",
                "♻️ آزاد کردن کاربر:\nبرای آزاد کردن کاربر محروم شده بنویسید:\nآزاد",
                "⚠️ صفر کردن تخلفات:\nبا سازنده ربات تماس بگیرید:\n@osine1",
            ]
            for section in quote_sections:
                pos = help_text.find(section)
                if pos != -1:
                    entities.append(
                        MessageEntityBlockquote(
                            offset=u16(help_text[:pos]),
                            length=u16(section)
                        )
                    )

            await event.reply(
                help_text,
                                                        formatting_entities=entities
            )
            return

        # فعال‌سازی گروه توسط مالک اصلی
        if clean_text == "فعال سازی":
            try:
                sender = await event.get_sender()
                print("OWNER DEBUG:", getattr(sender, "username", None), getattr(sender, "id", None), getattr(sender, "first_name", None))
                if not is_global_owner(getattr(sender, "username", None)):
                    await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                    return

                chat = await event.get_chat()
                gid = getattr(chat, "id", None)
                title = getattr(chat, "title", )

                if clean_text == "فعال سازی":
                    activate_group(gid, title)

                    await send_activation_message(bot, event, gid, title)

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return

        chat = await event.get_chat()
        sender = await event.get_sender()

        chat_id = getattr(chat, "id", None)

        # اجرای دستورات مدیریتی
        if clean_text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
            try:
                sender = await event.get_sender()
                await handle_admin_commands(bot, 
                    event,
                    clean_text,
                    getattr(sender, "id", 0),
                    chat_id
                )
                return
            except Exception as e:
                bot.logger.log_error(f"خطای اجرای دستور کلمات ممنوعه: {e}")

        if clean_text.startswith(("!", "/", ".")):
            try:
                sender = await event.get_sender()
                await handle_admin_commands(bot, 
                    event,
                    clean_text,
                    getattr(sender, "id", 0),
                    chat_id
                )
                return
            except Exception as e:
                bot.logger.log_error(f"خطای اجرای دستور مدیر: {e}")
        chat_title = getattr(chat, "title", "Unknown")

        user_id = getattr(sender, "id", None)
        username = (
            getattr(sender, "username", None)
            or getattr(sender, "first_name", "Unknown")
        )

        if clean_text == "ثبت مالک":
            if not is_global_owner(getattr(sender, "username", None)):
                await event.reply("❌ فقط مالک اصلی ربات اجازه ثبت مالک گروه را دارد")
                return

            if not event.reply_to:
                await event.reply("❌ برای ثبت مالک باید روی پیام کاربر ریپلای کنید")
                return

            try:
                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id,
                )
                target_user = await reply_msg.get_sender() if reply_msg else None
                if not target_user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                set_group_owner(chat_id, target_user.id)
                await event.reply(
                    f"✅ مالک گروه ثبت شد: {_format_group_member(target_user)}"
                )
            except Exception as e:
                bot.logger.log_error(f"خطا در ثبت مالک گروه: {e}")
                await event.reply(f"❌ خطا در ثبت مالک: {e}")
            return

        if clean_text == "لغو مالک":
            if not is_global_owner(getattr(sender, "username", None)):
                await event.reply("❌ فقط مالک اصلی ربات اجازه لغو مالک گروه را دارد")
                return

            removed_owner = remove_group_owner(chat_id)
            if removed_owner:
                await event.reply("✅ مالک گروه لغو شد")
            else:
                await event.reply("❌ برای این گروه مالک ثبت‌شده‌ای وجود ندارد")
            return

        # ثبت گروه توسط مالک ربات
        if clean_text == "ثبت گروه":

            try:
                if not is_global_owner(getattr(sender, "username", None)):
                    await event.reply(
                        "❌ فقط مالک ربات اجازه ثبت گروه دارد"
                    )
                    return

                chat = await event.get_chat()

                gid = getattr(chat, "id", None)
                title = getattr(chat, "title", )

                activate_group(
                    gid,
                    title
                )

                await event.reply(
                    f"✅ گروه «{title}» ثبت شد\\n"
                    f"🆔 {gid}"
                )

            except Exception as e:
                await event.reply(
                    f"❌ خطا در ثبت گروه: {e}"
                )

            return


        # فعال و غیرفعال کردن گروه توسط مالک اصلی
        # ثبت ادمین توسط مالک ربات

        if clean_text.startswith("ثبت ادمین"):
            if not _can_manage_group_admins(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply(
                    "❌ فقط مالک اصلی ربات یا مالک همین گروه اجازه مدیریت ادمین‌ها را دارد"
                )
                return

            try:
                admin_username = None

                if event.reply_to:
                    reply_msg = await bot.client.get_messages(
                            chat_id,
                            ids=event.reply_to.reply_to_msg_id
                        )
                    if reply_msg:
                        user = await reply_msg.get_sender()
                        admin_username = getattr(user, "username", None)

                if not admin_username:
                    parts = clean_text.split()
                    if len(parts) >= 3:
                        admin_username = parts[2].replace("@", "")

                if not admin_username:
                    await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                    return

                add_admin(chat_id, admin_username)
                await event.reply(f"✅ ادمین @{admin_username} ثبت شد")

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return


        # حذف ادمین توسط مالک اصلی یا مالک ثبت‌شده گروه
        if clean_text.startswith(("برکناری ادمین", "لغو ادمین")):
            if not _can_manage_group_admins(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply(
                    "❌ فقط مالک اصلی ربات یا مالک همین گروه اجازه مدیریت ادمین‌ها را دارد"
                )
                return

            try:
                admin_username = None

                if event.reply_to:
                    reply_msg = await bot.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    if reply_msg:
                        user = await reply_msg.get_sender()
                        admin_username = getattr(user, "username", None)

                if not admin_username:
                    parts = clean_text.split()
                    if len(parts) >= 3:
                        admin_username = parts[2].replace("@", "")

                if not admin_username:
                    await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                    return

                if remove_admin(chat_id, admin_username):
                    await event.reply(f"✅ دسترسی ادمین @{admin_username} حذف شد")
                else:
                    await event.reply("❌ این کاربر ادمین نیست")

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return


        # حذف چند پیام آخر با پاک عدد
        if clean_text.startswith("پاک "):
            try:
                sender_username = getattr(sender, "username", None)
                if not _can_delete_messages(
                    bot, chat_id, user_id, sender_username
                ):
                    await event.reply("❌ فقط مالک و ادمین‌ها اجازه حذف پیام دارند")
                    return

                parts = clean_text.split()
                if len(parts) != 2 or not parts[1].isdigit():
                    await event.reply("❌ استفاده: پاک + عدد مورد نیاز")
                    return

                requested_count = int(parts[1])
                if requested_count < 1 or requested_count > 700:
                    await event.reply("❌ تعداد پیام باید بین 1 تا 700 باشد")
                    return

                cooldown_key = (chat_id, user_id)
                now = _asyncio.get_running_loop().time()
                last_cleanup = DELETE_COMMAND_COOLDOWNS.get(cooldown_key)
                if last_cleanup is not None and now - last_cleanup < 5:
                    await event.reply(
                        "لطفا ۵ ثانیه صبر کنید تا پاکسازی قبلی کامل شود ⏳"
                    )
                    return
                DELETE_COMMAND_COOLDOWNS[cooldown_key] = now

                messages = await bot.client.get_messages(
                    chat_id,
                    limit=requested_count,
                )
                message_ids = [
                    message.id for message in messages
                    if getattr(message, "id", None)
                ]

                deleted_count = 0
                for start_index in range(0, len(message_ids), 100):
                    batch = message_ids[start_index:start_index + 100]
                    await bot.client.delete_messages(chat_id, batch)
                    deleted_count += len(batch)

                if deleted_count:
                    add_deleted_count(
                        chat_id, user_id, sender_username or "", deleted_count
                    )

                await event.reply(f"{deleted_count} پیام پاک شد 💣")
                return

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")
                return

        # حذف پیام با ریپلای
        if clean_text == "پاک":
            try:
                sender_username = getattr(sender, "username", None)
                if not _can_delete_messages(
                    bot, chat_id, user_id, sender_username
                ):
                    await event.reply("❌ فقط مالک و ادمین‌ها اجازه حذف پیام دارند")
                    return

                cooldown_key = (chat_id, user_id)
                now = _asyncio.get_running_loop().time()
                last_cleanup = DELETE_COMMAND_COOLDOWNS.get(cooldown_key)
                if last_cleanup is not None and now - last_cleanup < 5:
                    await event.reply(
                        "لطفا ۵ ثانیه صبر کنید تا پاکسازی قبلی کامل شود ⏳"
                    )
                    return
                DELETE_COMMAND_COOLDOWNS[cooldown_key] = now

                if not event.reply_to:
                    await event.reply("❌ باید روی پیام ریپلای کنید")
                    return

                await bot.client.delete_messages(
                    chat_id,
                    event.reply_to.reply_to_msg_id
                )

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return

# اخراج کاربر با ریپلای
        if clean_text == "اخراج":
            try:
                sender = await event.get_sender()
                sender_username = getattr(sender, "username", None)

                if not _has_group_management_permission(
                    bot, chat_id, user_id, sender_username
                ):
                    await event.reply("❌ فقط ادمین‌ها اجازه اخراج دارند")
                    return

                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                target_user = await reply_msg.get_sender()

                if not target_user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                add_kick(chat_id)
                await bot.client.edit_permissions(
                    chat_id,
                    target_user,
                    until_date=None,
                    view_messages=False
                )
                target_username = getattr(target_user, "username", None)
                target_display_name = " ".join(
                    part for part in (
                        getattr(target_user, "first_name", None),
                        getattr(target_user, "last_name", None),
                    ) if part
                ).strip()
                add_banned(
                    chat_id,
                    target_user.id,
                    username=target_username,
                    display_name=target_display_name,
                    reason="اخراج دستی توسط مالک یا ادمین",
                )

                await event.reply("✅ کاربر اخراج شد")

            except Exception as e:
                bot.logger.log_error(f"خطای اخراج: {e}")
                await event.reply(f"❌ خطا در اخراج:\n{e}")

            return


# آزاد کردن کاربر محروم شده
        if clean_text == "آزاد":
            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                ok = await bot.admin_actions.unban_user(
                    chat_id,
                    user.id,
                    getattr(user, "username", None),
                )

                if ok:

                    await event.reply("♻️ کاربر آزاد شد ✅")
                else:
                    await event.reply("❌ آزاد کردن انجام نشد")

            except Exception as e:
                await event.reply(f"❌ خطا در آزاد کردن:\n{e}")

            return

# اخطار کاربر با ریپلای
        if clean_text == "اخطار":
            sender_username = getattr(sender, "username", None)
            if not _has_group_management_permission(
                bot, chat_id, user_id, sender_username
            ):
                await event.reply("❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند")
                return

            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                username = getattr(user, "username", None) or "کاربر"

                print("WARN:", repr(chat_id), type(chat_id), repr(user.id), type(user.id))
                count = bot.tracker.increment(chat_id, user.id)
                threshold = bot.config_manager.get("spam_threshold", 5)

                await event.reply(
                    f"⚠️ کاربر @{username} اخطار دریافت کرد.\n"
                    f"تعداد اخطار: {count}/{threshold}"
                )

                if bot.tracker.should_punish(chat_id, user.id):
                    punished = await bot.admin_actions.punish_user(
                        chat_id, user.id, username, announce=False
                    )
                    if (
                        punished
                        and count >= 5
                        and bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                    ):
                        await _send_moderation_notification_once(
                            bot,
                            chat_id,
                            user.id,
                            "warning_ban",
                            event.message.id,
                            "🚫 کاربر "
                            f"{_format_banned_user(user, user.id)} "
                            "به دلیل تخلفات از گروه اخراج شد.",
                        )
                    bot.tracker.reset_count(chat_id, user.id)

            except Exception as e:
                await event.reply(f"❌ خطا در اخطار:\n{e}")

            return

# سکوت کاربر با ریپلای
        if clean_text == "سکوت":
            try:
                sender = await event.get_sender()

                sender_username = getattr(sender, "username", None)
                if not _has_group_management_permission(
                    bot, chat_id, user_id, sender_username
                ):
                    await event.reply("❌ فقط ادمین‌ها اجازه استفاده از سکوت را دارند")
                    return

                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                if not reply_msg:
                    await event.reply("❌ پیام ریپلای شده پیدا نشد")
                    return

                target_user = await reply_msg.get_sender()

                if not target_user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                # بررسی ادمین بودن (سازگار با SPlus)
                try:
                    admins = await bot.client.get_participants(chat_id)
                    admin_ids = [
                        getattr(x, "id", 0)
                        for x in admins
                        if getattr(x, "admin_rights", None)
                    ]

                    if target_user.id in admin_ids:
                        await event.reply("⚠️ این کاربر ادمین است و سکوت نشد")
                        return
                except Exception:
                    pass

                result = await bot.admin_actions.mute_user(
                    chat_id,
                    target_user.id
                )

                if result:
                    add_mute(chat_id)
                    await event.reply(
                        f"🔇 کاربر {getattr(target_user,'username','کاربر')} سکوت شد"
                    )
                else:
                    await event.reply("❌ انجام سکوت ناموفق بود")

            except Exception as e:
                bot.logger.log_error(
                    f"خطای سکوت کاربر: {e}"
                )
                await event.reply(f"❌ خطا در سکوت کاربر:\n{e}")

            return



        # رفع سکوت کاربر با ریپلای
        if clean_text == "رفع سکوت":
            sender_username = getattr(sender, "username", None)
            if not _has_group_management_permission(
                bot, chat_id, user_id, sender_username
            ):
                await event.reply("❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند")
                return

            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                if not reply_msg:
                    await event.reply("❌ پیام پیدا نشد")
                    return

                target_user = await reply_msg.get_sender()

                result = await bot.admin_actions.unmute_user(
                    chat_id,
                    target_user.id
                )

                if result:
                    add_mute(chat_id)
                    await event.reply("🔊 سکوت کاربر برداشته شد")
                else:
                    await event.reply("❌ رفع سکوت انجام نشد")

            except Exception as e:
                bot.logger.log_error(f"خطای رفع سکوت: {e}")
                await event.reply(f"❌ خطا در رفع سکوت:\n{e}")

            return

        # حذف دستی پیام با ریپلای و کلمه پاک
        if clean_text == "پاک":
            try:
                reply_id = getattr(
                    event.message,
                    "reply_to_msg_id",
                    None
                )

                if reply_id:
                    await bot.client.delete_messages(
                        chat.id,
                        [reply_id]
                    )

                    try:
                        await event.delete()
                    except Exception:
                        pass

                    await event.reply(
                        "✅ با موفقیت پاک شد"
                    )

                return

            except Exception as e:
                bot.logger.log_error(
                    f"DELETE COMMAND ERROR: {e}"
                )
                return


        # ضد اسپم پیام‌های پشت سرهم
        try:
            if not hasattr(bot, "flood_messages"):
                bot.flood_messages = {}

            if chat_id not in bot.flood_messages:
                bot.flood_messages[chat_id] = []

            bot.flood_messages[chat_id].append(
                (
                    _asyncio.get_running_loop().time(),
                    event.message.id,
                    user_id,
                    message_text.strip()
                )
            )

            now = _asyncio.get_running_loop().time()

            bot.flood_messages[chat_id] = [
                x for x in bot.flood_messages[chat_id]
                if now - x[0] <= 10
            ]

            user_msgs = [
                x for x in bot.flood_messages[chat_id]
                if x[2] == user_id
            ]

            # فقط پیام‌های تکراری یک کاربر حذف شوند
            if not is_group_moderator and len(user_msgs) >= 5:

                texts = [
                    x[3]
                    for x in user_msgs
                ]

                normalized = [
                    t.replace(" ", "")
                     .replace("\n", "")
                    for t in texts
                ]

                # پیام‌های متفاوت مکالمه عادی هستند
                if len(set(normalized)) > 2:
                    return

                ids = [
                    x[1]
                    for x in user_msgs
                ]

                await bot.client.delete_messages(
                    chat_id,
                    ids
                )

                bot.flood_messages[chat_id] = []

                if chat_id not in bot.delete_notice_lock:
                    bot.delete_notice_lock.add(chat_id)
                    await event.reply(
                        "⚠️ ارسال پیام تکراری پشت سرهم حذف شد"
                    )

                return

        except Exception as e:
            bot.logger.log_error(
                f"خطای ضد فلود: {e}"
            )

        except Exception as e:
            bot.logger.log_error(
                f"خطای حذف تکراری: {e}"
            )


        # فوروارد برای کاربر عادی از هر منبعی حذف می‌شود.
        try:
            if getattr(event.message, "fwd_from", None):
                if is_group_moderator:
                    print(f"✅ ADMIN FORWARD BYPASS: {sender_username}")
                    return

                await bot.client.delete_messages(chat_id, [event.message.id])
                await event.reply("⚠️ پیام فوروارد شده حذف شد")
                return

        except Exception as e:
            bot.logger.log_error(f"خطای حذف فوروارد: {e}")

        # بررسی تکرار شدید داخل یک پیام
        try:
            import re

            words = re.findall(r"\\w+|[آ-ی]+", message_text.lower())
            repeat_found = False

            for w in set(words):
                if len(w) >= 3 and words.count(w) >= 8:
                    repeat_found = True
                    break

            if repeat_found and not is_group_moderator:
                from modules.user_map import save_user

                save_user(chat_id, username, user_id)

                await bot.admin_actions.delete_message(
                    chat_id,
                    event=event
                )

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    punished = await bot.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username,
                        announce=False,
                    )
                    if (
                        punished
                        and bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                    ):
                        await _send_moderation_notification_once(
                            bot,
                            chat_id,
                            user_id,
                            "spam_ban",
                            event.message.id,
                            "🚫 کاربر "
                            f"{_format_banned_user(sender, user_id)} "
                            "به دلیل اسپم مکرر از گروه اخراج شد.",
                        )

                return

        except Exception as e:
            bot.logger.log_error(f"خطای بررسی تکرار داخلی: {e}")

        # بررسی کلمات فیلتر شده گروه
        group_word_spam = False
        group_word_reason = None

        # دستورات مدیریت کلمات نباید توسط فیلتر گرفته شوند
        word_admin_commands = (
            "فیلتر کلمه",
            "حذف کلمه",
            "افزودن کلمه",
            "ثبت کلمه",
            "لیست کلمات",
            "پاک کردن کلمات"
        )

        if any(message_text.startswith(x) for x in word_admin_commands):
            group_word_spam = False

        try:
            from modules.group_words_storage import get_words

            group_words = get_words(chat_id)

            for word in group_words:
                if word and word in message_text:
                    group_word_spam = True
                    group_word_reason = f"فیلتر گروه ({word})"
                    break

        except Exception as e:
            bot.logger.log_error(f"خطای بررسی کلمات گروه: {e}")

        # مدیر/مالک ثبت‌شده از فیلتر خودکار و فیلتر کلمات گروه عبور می‌کند.
        if is_group_moderator:
            print(f"✅ ADMIN BYPASS FILTER: {sender_username}")
            return

        # بررسی اسپم
        if group_word_spam:
            is_spam = True
            reason = group_word_reason
        else:
            is_spam, reason = bot.detector.is_spam(message_text, chat_id)

        if is_spam:

            # اسپم تکراری شدید: ذخیره + حذف + بن مستقیم
            try:
                from modules.user_map import save_user
                save_user(chat_id, username, user_id)

                # فقط متن‌های خیلی بلند و تکراری را اسپم شدید حساب کن
                normalized = message_text.strip()
                repeat_spam = (
                    len(normalized) > 300
                    and len(set(normalized.split())) < 20
                )

                if repeat_spam:
                    bot.logger.log_deleted_message(
                        user_id=user_id,
                        username=username,
                        group_id=chat_id,
                        group_title=chat_title,
                        original_text=message_text,
                        reason="اسپم تکراری شدید",
                        message_id=event.message.id
                    )

                    await bot.admin_actions.delete_message(chat_id, event=event)

                    if hasattr(bot.admin_actions, "ban_user"):
                        punish_key = f"{chat_id}:{user_id}"
                        if punish_key not in bot.punished_users:
                            bot.punished_users.add(punish_key)
                            banned = await bot.admin_actions.ban_user(
                                chat_id, user_id, reason="اسپم مکرر شدید"
                            )
                            if banned:
                                await _send_moderation_notification_once(
                                    bot,
                                    chat_id,
                                    user_id,
                                    "spam_ban",
                                    event.message.id,
                                    "🚫 کاربر "
                                    f"{_format_banned_user(sender, user_id)} "
                                    "به دلیل اسپم مکرر از گروه اخراج شد.",
                                )
                            else:
                                bot.punished_users.discard(punish_key)

                    return
            except Exception as e:
                print("repeat spam check error:", e)

            # افزایش شمارنده
            from modules.user_map import save_user

            save_user(chat_id, username, user_id)

            print("AUTO:", repr(chat_id), type(chat_id), repr(user_id), type(user_id))
            count = bot.tracker.increment(chat_id, user_id)

            threshold = bot.config_manager.get("spam_threshold", 3)

            # لاگ
            # لاگ
            bot.logger.log_deleted_message(
                user_id=user_id,
                username=username,
                group_id=chat_id,
                group_title=chat_title,
                original_text=message_text,
                reason=reason,
                message_id=event.message.id
            )

            # حذف پیام
            if bot.config_manager.get("delete_spam", True):
                await bot.admin_actions.delete_message(chat_id, event=event)

            # هشدار فقط ۵ بار
            if count <= 5:
                await bot.admin_actions.send_warning(
                    chat_id=chat_id,
                    username=username,
                    reason=reason,
                    count=count,
                    threshold=threshold,
                    reply_to=None
                )

            # بررسی مجازات
            if bot.tracker.should_punish(chat_id, user_id):
                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    print(
                        f"⚠️ کاربر {username}({user_id}) به آستانه {threshold} رسید - اعمال مجازات"
                    )

                    punished = await bot.admin_actions.punish_user(
                        chat_id, user_id, username, announce=False
                    )
                    if (
                        punished
                        and count >= 5
                        and bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                    ):
                        await _send_moderation_notification_once(
                            bot,
                            chat_id,
                            user_id,
                            "warning_ban",
                            event.message.id,
                            "🚫 کاربر "
                            f"{_format_banned_user(sender, user_id)} "
                            "به دلیل تخلفات از گروه اخراج شد.",
                        )

                    # بعد از بن دائمی گارد حفظ می‌شود تا پیام‌های صف‌شده
                    # دوباره بن/اعلان تولید نکنند؛ برای mute گارد آزاد می‌شود.
                    bot.tracker.reset_count(chat_id, user_id)
                    if not (
                        punished
                        and bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                    ):
                        bot.punished_users.discard(punish_key)
            # پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد
            pass

    except Exception as e:
        bot.logger.log_error(f"خطا در هندل پیام: {e}")
        import traceback
        traceback.print_exc()


