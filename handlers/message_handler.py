import asyncio as _asyncio
from collections import deque
from datetime import date

from modules.fill_blank import check_fill, get_token as get_fill_token
from modules.riddles import check_answer
from modules.group_stats import add_message, get_stats
from modules.group_storage import activate_group, deactivate_group
from modules.owner_check import is_global_owner
from modules.spam_history import save_history_message
from modules.spam_history import is_repeat
from modules.fill_blank import (
    TIMEOUT as FILL_TIMEOUT,
    clear as clear_fill,
    get_fill_answer,
    get_token as get_fill_token,
    new_fill,
)
from modules.riddles import (
    RIDDLE_TIMEOUT,
    clear as clear_riddle,
    get_answer,
    get_token as get_riddle_token,
    new_riddle,
)
from modules.multiple_choice import (
    ANSWER_SECONDS as QUIZ_SECONDS,
    EXHAUSTED_MESSAGE as QUIZ_EXHAUSTED_MESSAGE,
    answer_question,
    clear_question,
    get_active_question,
    is_exhausted as quiz_exhausted,
    start_question,
)
from modules.user_original_storage import (
    begin_registration,
    is_waiting_for_original,
    save_original,
    get_original,
)
from modules.jokes import get_joke
from modules.biographies import get_biography
from modules.simple_replies import SIMPLE_REPLIES, INSULTS, INSULT_REPLY
from modules.word_correction import start as start_correction, answer as answer_correction, get as get_correction, clear as clear_correction
from handlers.fox_games_router import (
    FOX_GAME_COMMANDS,
    handle as handle_fox_games,
)
# 📥 قابلیت مستقل «دانلود عکس».
from handlers.photo_download_handler import handle as handle_photo_download
# ⏳ تاریخ انقضای گروه — قابلیتی کاملاً مستقل با مسیر پردازش جدا.
from handlers.group_expiry_handler import (
    EXPIRED_NOTICE as GROUP_EXPIRED_NOTICE,
    blocks_message as group_expiry_blocks,
    handle as handle_group_expiry,
)
from modules.name_family import (
    cancel_round as cancel_name_family_round,
    finish as finish_name_family,
    is_active as name_family_active,
    schedule_round as schedule_name_family_round,
    start as start_name_family,
    submit as submit_name_family,
)
from modules.emoji_guess import (
    ANSWER_SECONDS as EMOJI_GUESS_SECONDS,
    REWARD_BRONZE as EMOJI_REWARD_BRONZE,
    EXHAUSTED_MESSAGE as EMOJI_GUESS_EXHAUSTED_MESSAGE,
    total_stages as _emoji_total_stages,
    answer as answer_emoji_guess,
    finish as finish_emoji_guess,
    is_active as emoji_guess_active,
    is_exhausted as emoji_guess_exhausted,
    reset_user as emoji_guess_reset,
    start as start_emoji_guess,
)
from modules.flag_guess import (
    get_active as get_flag_guess,
    EXHAUSTED_MESSAGE as FLAG_GUESS_EXHAUSTED_MESSAGE,
    answer as answer_flag_guess,
    finish as finish_flag_guess,
    is_active as flag_guess_active,
    is_exhausted as flag_guess_exhausted,
    start as start_flag_guess,
)
from economy import name_filter
from modules.group_memory import extract_name, friendly_reply, get_name as get_memory_name, remove_name as remove_memory_name, set_name as set_memory_name
from modules.group_rules import begin as begin_rules, cancel as cancel_rules, format_rules, remove as remove_rules, save as save_rules, waiting as waiting_rules
from modules.name_insights import report as name_personality_report
from modules.did_you_know import get_fact
from modules.user_activity import record as record_activity, get as get_activity
from modules.reminders import begin as begin_reminder, waiting as waiting_reminder, capture as capture_reminder
from modules.translation import begin as begin_translation, waiting as waiting_translation, clear as clear_translation, translate_to_persian
# 💰 اقتصاد: تنها از راه API عمومی. هیچ دسترسی مستقیمی به دیتابیس نیست.
import economy
from economy import (
    get_profile as get_coin_profile,
    get_rank as coin_rank,
    leaderboard as coin_leaderboard,
    record_message as record_coin_message,
)
from handlers.economy_handler import handle as handle_economy
from modules.gif_spam_detector import (
    handle_gif as handle_gif_message,
    is_gif_message,
    pending_count as gif_pending_count,
    reset_gif_history,
    track_gif,
)
from modules.group_stats import add_kick, add_mute, make_report, add_deleted_count
from modules.spam_history import get_message_ids, get_user_history, clear_user
from modules.web_search import can_search, search_web
from modules.jorat_haghighat import get_jorat, get_haghighat
from modules.font_converter import make_fonts
from modules.admin_storage import add_admin, remove_admin, is_admin, load_admins
from modules.banned_storage import add_banned, load_banned, save_banned
from modules.removed_users_reset import reset_system_removed_users
from modules.group_storage import set_group_owner, get_group_owner, remove_group_owner
from modules.owner_greetings import registered_owner_greeting_response
from modules.group_id import normalize_group_id
from modules.pinned_messages import save as save_pinned_message, get as get_pinned_message
from modules.performance import MessagePerformance
from modules.outgoing_profiler import (
    begin_response_measurement,
    end_response_measurement,
    response_rpc_ms,
)
from handlers.admin_handler import handle_admin_commands
from splusthon.tl.types import MessageEntityBold, MessageEntityBlockquote
from splusthon.tl import functions
from splusthon import types


def _math_digits(value):
    """نمایش عدد فقط برای متن اعلان‌ها، بدون تغییر مقدار منطقی."""
    return str(value).translate(str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"))


def _jalali_today():
    """تاریخ امروز ایران در تقویم جلالی، بدون وابستگی خارجی."""
    gy, gm, gd = date.today().year, date.today().month, date.today().day
    g_days = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
        + (gy2 + 399) // 400 + gd + g_days[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


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


def _format_admin_display(user):
    """نمایش امن ادمین بدون افشای شناسهٔ عددی."""
    username = getattr(user, "username", None)
    if username and not str(username).strip().isdigit():
        return f"@{str(username).lstrip('@')}"

    display_name = " ".join(
        part for part in (
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ) if part
    ).strip()
    return display_name or "Unknown User"


async def _reward_game_reply(event, chat_id, user_id, user, game,
                             reference=None, amount=None):
    """جایزهٔ بازی را با نوع سکهٔ درست پرداخت و موجودی را اعلام می‌کند.

    نوع سکه از ``economy.rewards`` می‌آید: بازی عادی برنز، بازی سخت نقره.
    """
    from economy import rewards as _rewards
    coin_type = _rewards.coin_for(game)
    paid = _rewards.amount_for(game) if amount is None else int(amount)

    # موجودی «قبل» را می‌خوانیم تا بتوانیم بفهمیم پرداخت واقعاً انجام
    # شده یا دفتر تراکنش آن را تکراری دیده است.
    before = economy.get_balance(chat_id, user_id)[coin_type]
    economy.award_game(
        chat_id, user_id, game, reference=reference, amount=amount,
        name=_format_admin_display(user),
    )
    # موجودی از دیتابیس دوباره خوانده می‌شود، نه از مقدار کش‌شده.
    balance = economy.get_balance(chat_id, user_id)
    gained = balance[coin_type] - before

    coin_label = _rewards.coin_name(coin_type)
    icon = "🥈" if coin_type == economy.SILVER else "🥉"

    if gained <= 0:
        # هرگز نباید «+n سکه» بگوییم وقتی چیزی اضافه نشده. اگر اینجا
        # رسیدیم یعنی مرجع تکراری بوده و جایزهٔ این دور قبلاً پرداخت شده.
        bot_logger = getattr(event, "_bot_logger", None)
        if bot_logger is not None:
            bot_logger.log_error(
                f"REWARD NOT APPLIED game={game} chat_id={chat_id} "
                f"user_id={user_id} reference={reference!r}"
            )
        await event.reply(
            "🎉 پاسخ صحیح بود.\n\n"
            "🪙 جایزهٔ این دور قبلاً به حساب شما اضافه شده است.\n\n"
            f"💰 موجودی {coin_label}:\n{icon} "
            f"{_math_digits(balance[coin_type])}\n\n"
            f"💎 ارزش کل:\n{_math_digits(balance['total_coin_value'])}"
        )
        return balance

    await event.reply(
        "🎉 پاسخ صحیح بود.\n\n"
        f"🪙 شما +{_math_digits(gained)} سکه {coin_label} دریافت کردید.\n\n"
        f"💰 موجودی {coin_label}:\n{icon} {_math_digits(balance[coin_type])}\n\n"
        f"💎 ارزش کل:\n{_math_digits(balance['total_coin_value'])}"
    )
    return balance


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


def _get_forward_metadata(message):
    fields = {
        field: getattr(message, field, None)
        for field in (
            "fwd_from",
            "forward_from",
            "forward_chat",
            "forwarded",
            "is_forward",
        )
    }
    for field, value in fields.items():
        if value:
            return True, field, fields
    return False, None, fields


def _log_ban_execution(bot, chat_id, user_id, reason):
    punish_key = f"{chat_id}:{user_id}"
    bot.logger.log_info(
        "BAN EXECUTION DEBUG\n"
        f"chat_id={chat_id}\n"
        f"user_id={user_id}\n"
        f"reason={reason}\n"
        f"already_punished={punish_key in bot.punished_users}\n"
        f"will_ban={punish_key not in bot.punished_users}"
    )


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


def _run_background(bot, name, callback, *args):
    """کارهای غیرامنیتیِ پس از پاسخ را از مسیر پیام جدا می‌کند."""
    async def run():
        try:
            callback(*args)
        except Exception as error:
            bot.logger.log_error(f"BACKGROUND {name} FAILED: {error}")
    return _asyncio.create_task(run())


def _chat_game_busy(chat_id):
    """آیا یکی از بازی‌های «چت‌محور» همین حالا در این گروه فعال است.

    این بازی‌ها state خود را با کلید chat_id نگه می‌دارند، پس اجرای دوبارهٔ
    دستور، دور قبلی را بازنویسی و خراب می‌کرد. بازی‌های کاربرمحور (چیستان،
    جای خالی و حدس ایموجی) عمداً در این فهرست نیستند؛ آن‌ها با کلید
    (chat_id, user_id) کار می‌کنند و چند کاربر می‌توانند هم‌زمان بازی کنند.
    """
    return (
        name_family_active(chat_id)
        or flag_guess_active(chat_id)
        or get_correction(chat_id) is not None
        or get_active_question(chat_id) is not None
    )


GAME_BUSY_MESSAGE = "⏳ یک بازی دیگر در این گروه در جریان است؛ لطفاً تا پایان آن صبر کنید."


EMOJI_GUESS_TOTAL = _emoji_total_stages()

# فقط این دستورها اجازهٔ ریست کردن پیشرفت را دارند.
EMOJI_RESET_COMMANDS = {
    "شروع دوباره حدس ایموجی",
    "ریست حدس ایموجی",
}


def puzzle_token_for(chat_id, user_id=None):
    """توکن معمای فعال همین کاربر (برای لاگ و مرجع)."""
    import modules.emoji_guess as _eg
    state = _eg.active_state(chat_id, user_id) if user_id is not None else None
    return state["token"] if state else 0


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


async def _cleanup_heavy_spam_history(bot, event, chat_id, user_id):
    history = get_user_history(chat_id, user_id)
    if history is None:
        print("HEAVY SPAM CLEANUP\n"
              f"User: {user_id}\nStored messages: 0\nDeleted messages: 0\n"
              "Failed deletions: 0\nReason: no history found")
        return
    if not history:
        print("HEAVY SPAM CLEANUP\n"
              f"User: {user_id}\nStored messages: 0\nDeleted messages: 0\n"
              "Failed deletions: 0\nReason: history empty")
        return

    raw_ids = [item.get("message_id") for item in history]
    valid_ids = [message_id for message_id in raw_ids if isinstance(message_id, int) and message_id > 0]
    invalid_count = len(raw_ids) - len(valid_ids)
    if not valid_ids:
        print("HEAVY SPAM CLEANUP\n"
              f"User: {user_id}\nStored messages: {len(history)}\nDeleted messages: 0\n"
              f"Failed deletions: {invalid_count}\nReason: message ids missing or invalid")
        clear_user(chat_id, user_id)
        return

    deleted_count = 0
    failed_count = invalid_count
    for start in range(0, len(valid_ids), 100):
        batch = valid_ids[start:start + 100]
        try:
            await bot.client.delete_messages(chat_id, batch)
            deleted_count += len(batch)
        except Exception as error:
            failed_count += len(batch)
            bot.logger.log_error(
                f"خطای حذف دسته‌ای heavy spam {user_id}: {error}"
            )
        await _asyncio.sleep(0.2)

    print("HEAVY SPAM CLEANUP\n"
          f"User: {user_id}\nStored messages: {len(history)}\n"
          f"Deleted messages: {deleted_count}\nFailed deletions: {failed_count}")
    if deleted_count:
        await event.reply(f"🗑 {_math_digits(deleted_count)} پیام هرزنامه پاک شد")
    elif failed_count:
        print("HEAVY SPAM CLEANUP reason: delete failed")

    clear_user(chat_id, user_id)


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


# ---------------------------------------------------------------------------
# Command routing
#
# «ثبت اسم علی» و «ثبت ادمین» هر دو با «ثبت » شروع می‌شوند. اگر مسیر حافظهٔ گروه
# با startswith("ثبت ") کار کند، دستور «ثبت ادمین» را می‌بلعد و چون آن مسیر در
# پایان return می‌کند، هرگز به admin handler نمی‌رسد.
#
# راه‌حل: هر دستور چندکلمه‌ای و حساس اینجا صریح ثبت می‌شود و *پیش از* هر
# الگوی عمومی بررسی می‌گردد. ترتیب این tuple اهمیت دارد: طولانی‌ترین و
# دقیق‌ترین دستور اول.
# ---------------------------------------------------------------------------

# (متن دقیق دستور، نام handler مقصد) — هیچ‌کدام نباید به مسیر حافظهٔ گروه بروند.
RESERVED_COMMANDS = (
    # --- مدیریت ادمین و مالک ---
    ("ثبت ادمین", "admin_registration"),
    ("لغو ادمین", "admin_removal"),
    ("برکناری ادمین", "admin_removal"),
    ("ثبت مالک", "group_owner.set"),
    ("لغو مالک", "group_owner.remove"),
    ("برکناری مالک", "group_owner.remove"),
    ("لیست ادمین", "admin_list"),
    # --- مدیریت گروه ---
    ("ثبت گروه", "group_registration"),
    ("حذف گروه", "group_removal"),
    ("ثبت قوانین", "group_rules.set"),
    ("حذف قوانین", "group_rules.remove"),
    ("قوانین", "group_rules.show"),
    # --- حافظه و اطلاعات کاربر ---
    ("ثبت اصل", "user_original.set"),
    ("اصلم", "user_original.show"),
    ("حذف حافظه", "group_memory.remove_other"),
    ("حذف اسم", "group_memory.remove_self"),
    ("حافظه من", "group_memory.show"),
)

# واژهٔ دوم در «ثبت …» که هرگز یک اسم نیست، بلکه نشانهٔ یک دستور مدیریتی است.
# این نگهبان ساختاری تضمین می‌کند حتی اگر دستور تازه‌ای به کد اضافه شود و
# ثبتش در RESERVED_COMMANDS فراموش شود، باز هم به مسیر «ثبت اسم» نشت نکند.
ADMIN_OBJECT_WORDS = frozenset({
    "ادمین", "ادمین‌ها", "ادمینها", "مدیر", "مدیران",
    "مالک", "مالکیت", "صاحب",
    "گروه", "گپ", "چت", "کانال",
    "قوانین", "قانون", "رول", "رولز",
    "اصل", "اصلیت",
    "کاربر", "عضو", "ربات", "بات",
    "فیلتر", "کلمه", "کلمات", "لیست",
})

# پیشوندهایی که مسیر حافظهٔ گروه می‌پذیرد، به ترتیب دقیق‌بودن.
MEMORY_REGISTER_PREFIXES = ("ثبت اسم ", "ثبت ")

# فاصلهٔ مجازی/نیم‌فاصله و نویسه‌های عربی که کاربر ممکن است تایپ کند.
_NORMALIZE_MAP = {
    "\u200c": " ",  # ZWNJ
    "\u200f": "",   # RTL mark
    "\u200e": "",   # LTR mark
    "\u064a": "\u06cc",  # Arabic yeh -> Persian yeh
    "\u0643": "\u06a9",  # Arabic kaf -> Persian kaf
}


def normalize_command(text):
    """متن را برای مقایسهٔ دقیق دستور یکسان‌سازی می‌کند.

    فاصله‌های تکراری، نیم‌فاصله و نویسه‌های عربی حذف/تبدیل می‌شوند تا
    «ثبت  ادمین» و «ثبت ادمين» هم درست تشخیص داده شوند. متن اصلی دست‌نخورده
    می‌ماند؛ این فقط برای تصمیم‌گیری routing است.
    """
    if not text:
        return ""
    normalized = str(text)
    for source, target in _NORMALIZE_MAP.items():
        normalized = normalized.replace(source, target)
    return " ".join(normalized.split())


def match_reserved_command(text):
    """اگر متن یک دستور رزروشده باشد، (دستور، handler) را برمی‌گرداند.

    تطبیق دقیق است: یا کل متن برابر دستور است، یا دستور به‌همراه یک آرگومان
    آمده (مثل «ثبت ادمین @ali»). «ثبت اسمی» یا «ثبت ادمینها» تطبیق نمی‌کند.
    """
    normalized = normalize_command(text)
    for command, handler in RESERVED_COMMANDS:
        if normalized == command or normalized.startswith(command + " "):
            return command, handler
    return None, None


def resolve_registration_prefix(text):
    """پیشوند حافظهٔ گروه را برمی‌گرداند، یا None اگر دستور رزروشده باشد.

    این تنها نقطه‌ای است که تصمیم می‌گیرد یک پیام «ثبت …» به حافظهٔ گروه برود.
    """
    # ۱) هر دستور رزروشده مطلقاً بیرون از مسیر ثبت اسم است.
    command, _handler = match_reserved_command(text)
    if command is not None:
        return None

    normalized = normalize_command(text)
    # ۲) «ثبت» یا «ثبت اسم» بدون نام، ثبت نیست.
    if normalized in {"ثبت", "ثبت اسم"}:
        return None

    for prefix in MEMORY_REGISTER_PREFIXES:
        if not normalized.startswith(prefix):
            continue
        remainder = normalized[len(prefix):].strip()
        if not remainder:
            return None
        # ۳) نگهبان ساختاری: «ثبت <واژهٔ مدیریتی>» هرگز ثبت اسم نیست، حتی اگر
        #    آن دستور هنوز در RESERVED_COMMANDS ثبت نشده باشد.
        if prefix == "ثبت " and remainder.split()[0] in ADMIN_OBJECT_WORDS:
            return None
        return prefix
    return None


def _log_command_route(bot, text, matched_command, handler):
    """ردیابی تصمیم routing برای هر دستور حساس."""
    try:
        bot.logger.log_info(
            "COMMAND ROUTE MATCH "
            f"text={text[:60]!r} "
            f"matched_command={matched_command!r} "
            f"handler={handler!r}"
        )
    except Exception:
        pass


def _can_manage_group_admins(bot, chat_id, user_id, username):
    if is_global_owner(user_id):
        return True

    group_owner_id = get_group_owner(chat_id)
    return group_owner_id is not None and str(user_id) == str(group_owner_id)


DELETE_COMMAND_COOLDOWNS = {}
# قفلِ گروه برای اجرای پاک: فقط یک عملیات حذف در هر گروه در لحظه اجرا می‌شود
# تا چند ادمینِ هم‌زمان روی هم نیفتند و خطای RPC ندهند.
_DELETE_GROUP_LOCKS = {}
# سقفِ حافظهٔ cooldown تا بی‌نهایت رشد نکند.
DELETE_COOLDOWN_MAX_ENTRIES = 2000
ADMIN_PERMISSION_CACHE = {}
ADMIN_PERMISSION_CACHE_TTL_SECONDS = 45


def _has_group_management_permission(bot, chat_id, user_id, username):
    normalized_username = (username or "").lstrip("@").lower()
    cache_key = (chat_id, user_id, normalized_username)
    now = _asyncio.get_running_loop().time()
    cached = ADMIN_PERMISSION_CACHE.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    group_owner_id = get_group_owner(chat_id)
    if is_global_owner(user_id):
        result, source = True, "global_owner"
    elif group_owner_id is not None and str(user_id) == str(group_owner_id):
        result, source = True, "registered_group_owner"
    elif is_admin(chat_id, user_id, username):
        result, source = True, "registered_group_admin"
    else:
        result, source = False, "none"

    ADMIN_PERMISSION_CACHE[cache_key] = (
        now + ADMIN_PERMISSION_CACHE_TTL_SECONDS, result
    )
    # این helper برای هر پیام گروهی اجرا می‌شود؛ log synchronous فقط برای
    # permission مثبت نگه داشته می‌شود تا مسیر عادی کاربران I/O اضافی نداشته باشد.
    if result:
        bot.logger.log_info(
            "ADMIN CHECK DEBUG "
            f"user_id={user_id} username={username} group_id={chat_id} "
            f"result={result} source={source}"
        )
    return result


def _can_delete_messages(bot, chat_id, user_id, username):
    return _has_group_management_permission(
        bot, chat_id, user_id, username
    )


def _delete_group_lock(chat_id):
    """قفلِ per-group برای اجرای پاک (ایجاد lazy)."""
    lock = _DELETE_GROUP_LOCKS.get(chat_id)
    if lock is None:
        lock = _asyncio.Lock()
        _DELETE_GROUP_LOCKS[chat_id] = lock
    return lock


def _prune_delete_cooldowns():
    """حافظهٔ cooldown را محدود نگه می‌دارد تا بی‌نهایت رشد نکند.

    ورودی‌های قدیمی‌تر از پنجرهٔ ۶۰ ثانیه حذف می‌شوند و اگر همچنان بیش از
    سقف باقی بماند، قدیمی‌ترین‌ها پاک می‌شوند.
    """
    now = _asyncio.get_running_loop().time()
    cutoff = now - 60
    stale = [k for k, ts in DELETE_COMMAND_COOLDOWNS.items() if ts < cutoff]
    for k in stale:
        DELETE_COMMAND_COOLDOWNS.pop(k, None)
    while len(DELETE_COMMAND_COOLDOWNS) > DELETE_COOLDOWN_MAX_ENTRIES:
        try:
            oldest = min(DELETE_COMMAND_COOLDOWNS, key=DELETE_COMMAND_COOLDOWNS.get)
            DELETE_COMMAND_COOLDOWNS.pop(oldest, None)
        except (KeyError, ValueError):
            break
    # قفل‌های گروه‌هایی که cooldown آن‌ها دیگر در حافظه نیست هم پاک می‌شوند
    # تا _DELETE_GROUP_LOCKS بی‌نهایت رشد نکند.
    if len(_DELETE_GROUP_LOCKS) > DELETE_COOLDOWN_MAX_ENTRIES:
        keys = list(_DELETE_GROUP_LOCKS.keys())
        for k in keys[:len(keys) - DELETE_COOLDOWN_MAX_ENTRIES]:
            _DELETE_GROUP_LOCKS.pop(k, None)


def _delete_cooldown_allowed(chat_id):
    """بررسی/ثبت cooldown برای کل گروه (نه هر کاربر).

    اگر کمتر از ۵ ثانیه از آخرین پاکِ همین گروه گذشته باشد، False برمی‌گرداند
    (یعنی باید پیام «صبر کنید» بدهیم). در غیر این صورت زمان را ثبت و True
    برمی‌گرداند.
    """
    now = _asyncio.get_running_loop().time()
    last_cleanup = DELETE_COMMAND_COOLDOWNS.get(chat_id)
    if last_cleanup is not None and now - last_cleanup < 5:
        return False
    DELETE_COMMAND_COOLDOWNS[chat_id] = now
    _prune_delete_cooldowns()
    return True


async def handle_new_message(bot, event):
    """هندلر اصلی برای پیام‌های جدید"""
    profiler = MessagePerformance()
    response_token = begin_response_measurement()
    chat_id = getattr(event, "chat_id", None)
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

        event_chat = await event.get_chat()
        chat_id = getattr(event_chat, "id", event.chat_id)
        sender = await event.get_sender()
        user_id = sender.id if sender else 0
        sender_username = (getattr(sender, "username", None) or "").lstrip("@").lower()
        profiler.mark("RECEIVE")
        # حساب خود ربات هرگز نباید وارد مسیرهای activity، فیلتر یا مجازات شود.
        is_bot_account = (
            user_id == getattr(bot, "bot_account_id", None)
            or sender_username in {"aifox", "osine1"}
        )
        # مالک اصلی باید به فرمان‌ها برسد؛ bypass امنیتی او از مسیر moderator
        # اعمال می‌شود، نه با return پیش از handler.
        if is_bot_account and not is_global_owner(user_id):
            if message_text.strip() == "اسم فامیل" or len(message_text.splitlines()) >= 7:
                bot.logger.log_info(
                    "NAME FAMILY TRACE HANDLER_BLOCK "
                    f"reason=bot_account chat_id={chat_id} user_id={user_id}"
                )
            return
        clean_text = message_text.strip()

        # ------------------------------------------------------------------
        # 📥 دانلود عکس — اتصالِ زودهنگام تا پیامِ مرحله‌ای (عبارت/تأیید/لغو)
        # پیش از spam/repeat/سایر شاخه‌ها به هندلرِ مستقل برسد. فقط وقتی
        # جریانِ دانلودِ این کاربر فعال است یا خودِ دستور ارسال شده.
        # ------------------------------------------------------------------
        from modules import photo_download as _photo_dl
        if (clean_text == _photo_dl.COMMAND
                or _photo_dl.session(chat_id, user_id) is not None):
            if await handle_photo_download(
                bot, event, chat_id, user_id, sender, clean_text, bot.logger
            ):
                return

        # ------------------------------------------------------------------
        # 📇 دفترچهٔ یوزرنیم — پیش از هر شاخهٔ دستوری.
        #
        # انتقال سکه با یوزرنیم انجام می‌شود، پس مقصد باید شناخته شده
        # باشد. اگر این ثبت پشت گیت fast_command و بعد از دَه‌ها return
        # می‌ماند، کاربری که فقط دستور می‌فرستد هرگز ثبت نمی‌شد و
        # نمی‌شد به او سکه فرستاد. نوشتن defer است، پس مسیر داغ را کند
        # نمی‌کند.
        # ------------------------------------------------------------------
        if not event.is_private:
            try:
                economy.directory.remember(
                    chat_id, user_id, getattr(sender, "username", None),
                )
            except Exception as error:
                bot.logger.log_error(f"USERNAME DIRECTORY FAILED {error!r}")

        # ------------------------------------------------------------------
        # ⏳ تاریخ انقضای گروه — پیش از هر دستور دیگری.
        #
        # مسیر این سه دستور کاملاً جداست و تطبیق دقیق است، پس هیچ
        # startswith عمومی نمی‌تواند آن‌ها را با دستور دیگری اشتباه بگیرد.
        # ------------------------------------------------------------------
        if not event.is_private:
            if await handle_group_expiry(
                bot, event, chat_id, sender, clean_text, bot.logger
            ):
                return
            # گروه منقضی: همهٔ قابلیت‌ها متوقف می‌شوند تا مالک اصلی دوباره
            # یکی از سه دستور را بفرستد.
            if group_expiry_blocks(chat_id, sender):
                return

        # ------------------------------------------------------------------
        # 💰 اقتصاد — دو بخش مستقل «موجودی» و «فروشگاه».
        # پیش از بازی‌ها بررسی می‌شود تا گفتگوی باز منو با پاسخ بازی‌ها
        # تداخل نکند.
        # ------------------------------------------------------------------
        if await handle_economy(
            bot, event, chat_id, user_id, sender, clean_text, bot.logger
        ):
            return

        name_family_trace = (
            clean_text == "اسم فامیل" or name_family_active(chat_id)
        )
        if name_family_trace:
            bot.logger.log_info(
                "NAME FAMILY TRACE HANDLER_ENTER "
                f"chat_id={chat_id} user_id={user_id} message_id={getattr(event.message, 'id', None)} "
                f"line_count={len(clean_text.splitlines())} char_count={len(clean_text)} "
                f"round_active={name_family_active(chat_id)}"
            )

        # حافظهٔ گروه: هر کاربر فقط نام متصل به user_id خودش را ثبت می‌کند.
        # ⚠️ دستورهای رزروشده (مثل «ثبت ادمین») هرگز نباید به این مسیر برسند؛
        # تفکیک آن‌ها در resolve_registration_prefix انجام می‌شود.
        register_prefix = resolve_registration_prefix(clean_text)
        if register_prefix is not None:
            _log_command_route(bot, clean_text, f"{register_prefix.strip()} …",
                               "group_memory.set_name")
            if event.is_private:
                await event.reply("❌ حافظه گروه فقط داخل گروه فعال است.")
                return
            display_name, error = extract_name(clean_text[len(register_prefix):])
            if error == "too_long":
                await event.reply("❌ نام خیلی طولانی است.")
            elif error == "restricted":
                await event.reply(name_filter.MESSAGE_RESTRICTED)
            elif error == "banned":
                await event.reply(name_filter.MESSAGE_BANNED)
            elif error:
                await event.reply("❌ نام معتبر نیست، لطفاً یک اسم یا لقب مناسب وارد کنید.")
            else:
                set_memory_name(chat_id, user_id, display_name)
                await event.reply(f"✅ حافظه شما ثبت شد: {display_name}")
            return

        if clean_text == "حافظه من":
            saved_name = get_memory_name(chat_id, user_id)
            await event.reply(
                f"🧠 حافظه شما: {saved_name}" if saved_name else "🧠 هنوز اسمی ثبت نکردی."
            )
            return

        if clean_text == "حذف اسم":
            if remove_memory_name(chat_id, user_id):
                await event.reply("✅ حافظه شما حذف شد.")
            else:
                await event.reply("🧠 حافظه‌ای برای حذف ندارید.")
            return

        if clean_text.startswith("شخصیت "):
            report = name_personality_report(clean_text.replace("شخصیت ", "", 1))
            await event.reply(report or "❌ نام معتبر وارد کنید.")
            return

        if clean_text == "دانستنی":
            await event.reply(f"🧠 دانستنی:\n\n{get_fact()}")
            return

        saved_name = get_memory_name(chat_id, user_id)
        personal_reply = friendly_reply(saved_name, clean_text) if saved_name else None
        if personal_reply:
            await event.reply(personal_reply)
            return

        fast_command = (
            clean_text in SIMPLE_REPLIES
            or clean_text in INSULTS
            or clean_text in {"راهنما", "/help", "!help", "help", "لیست کاربران", "لیست ادمینی", "آمارم", "راهنمای امتیاز", "امتیاز من", "رتبه ها", "بیوگرافی", "یاد آوری", "ترجمه", "قفل", "باز", "لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "جک", "تصحیح کلمات", "اسم فامیل", "حدس ایموجی", "حدس پرچم", "دانستنی", "حافظه من", "حذف اسم", "قوانین", "ثبت قوانین", "حذف قوانین", "حذف حافظه", "موجودی", "فروشگاه"} | EMOJI_RESET_COMMANDS | FOX_GAME_COMMANDS
            or (
                clean_text.startswith(("!", "/", "."))
                and not clean_text.startswith(("/فیلتر ", "/رفع "))
                and clean_text != "/فیلترها"
            )
        )
        # پاسخ ویژه فقط برای مالکِ ثبت‌شدهٔ همین گروه، پیش از پاسخ‌های عمومی.
        registered_owner_id = get_group_owner(chat_id) if not event.is_private else None
        owner_reply = registered_owner_greeting_response(
            clean_text,
            user_id,
            registered_owner_id,
            is_private=event.is_private,
        )
        if owner_reply:
            await event.reply(owner_reply)
            return

        # پاسخ‌های ثابت بدون ورود به moderation و I/O پاسخ می‌گیرند.
        profiler.mark("COMMAND_MATCH")
        simple_reply = SIMPLE_REPLIES.get(clean_text)
        if simple_reply:
            await event.reply(simple_reply)
            return
        if clean_text in INSULTS:
            await event.reply(INSULT_REPLY)
            return

        # فرمان‌های کوتاه نباید برای ثبت آمار/فعالیت منتظر I/O فایل بمانند.
        if not event.is_private and not fast_command:
            _run_background(
                bot, "user_activity", record_activity, chat_id, user_id, event.message
            )
        sender_username = getattr(sender, "username", None)
        # فرمان‌های سریع permission مخصوص خود را در branch فرمان بررسی می‌کنند.
        is_group_moderator = (
            not event.is_private
            and not fast_command
            and _has_group_management_permission(
                bot, chat_id, user_id, sender_username
            )
        )
        profiler.mark("ADMIN_CHECK")
        if not is_group_moderator and not is_gif_message(event.message):
            reset_gif_history(chat_id, user_id)

        # قوانین گروه فقط توسط مدیر/مالک ثبت، تغییر یا حذف می‌شوند.
        can_manage_group = (
            not event.is_private
            and _has_group_management_permission(
                bot, chat_id, user_id, getattr(sender, "username", None)
            )
        )
        if clean_text == "ثبت قوانین":
            _log_command_route(bot, clean_text, "ثبت قوانین", "group_rules.set")
            if not can_manage_group:
                await event.reply("❌ فقط مدیر گروه اجازه ثبت قوانین دارد.")
            else:
                begin_rules(chat_id, user_id)
                await event.reply("📜 لطفاً قوانین گروه را ارسال کنید.")
            return

        if waiting_rules(chat_id, user_id):
            if not can_manage_group:
                cancel_rules(chat_id, user_id)
                await event.reply("❌ فقط مدیر گروه اجازه ثبت قوانین دارد.")
            elif save_rules(chat_id, user_id, message_text):
                await event.reply("📜 قوانین گروه ثبت شد ✅")
            else:
                await event.reply("❌ متن قوانین معتبر نیست یا خیلی طولانی است.")
            return

        if clean_text == "حذف قوانین":
            _log_command_route(bot, clean_text, "حذف قوانین", "group_rules.remove")
            if not can_manage_group:
                await event.reply("❌ فقط مدیر گروه اجازه حذف قوانین دارد.")
            elif remove_rules(chat_id):
                await event.reply("✅ قوانین گروه حذف شد.")
            else:
                await event.reply("📜 قانونی برای حذف ثبت نشده است.")
            return

        if clean_text == "قوانین":
            await event.reply(format_rules(chat_id) or "📜 هنوز قانونی برای این گروه ثبت نشده است.")
            return

        # مدیر با ریپلای روی پیام کاربر می‌تواند حافظهٔ همان کاربر را حذف کند.
        if clean_text == "حذف حافظه":
            if not can_manage_group:
                await event.reply("❌ فقط مدیر گروه اجازه مدیریت حافظه‌ها را دارد.")
                return
            if not event.reply_to:
                await event.reply("❌ روی پیام کاربر ریپلای کنید.")
                return
            reply_msg = await bot.client.get_messages(chat_id, ids=event.reply_to.reply_to_msg_id)
            target_user = await reply_msg.get_sender() if reply_msg else None
            if not target_user:
                await event.reply("❌ کاربر پیدا نشد.")
            elif remove_memory_name(chat_id, target_user.id):
                await event.reply("✅ حافظه کاربر حذف شد.")
            else:
                await event.reply("🧠 حافظه‌ای برای این کاربر ثبت نشده است.")
            return

        if (
            not message_text
            and not _get_forward_metadata(event.message)[0]
            and not is_gif_message(event.message)
        ):
            return

        if not fast_command:
            save_history_message(chat_id, user_id, event.message.id, message_text)
        if not is_group_moderator:
            if is_gif_message(event.message):
                # مسیر مستقل GIF: ثبت، صف‌بندی و حذف دسته‌ای با تلاش مجدد.
                repeated_gif_ids, newly_flagged = handle_gif_message(
                    chat_id,
                    user_id,
                    event.message.id,
                    client=bot.client,
                    logger=bot.logger,
                )
                deleted = len(repeated_gif_ids)
                if repeated_gif_ids:
                    bot.logger.log_info(
                        f"GIF SPAM QUEUED chat_id={chat_id} user_id={user_id} "
                        f"ids={repeated_gif_ids} newly_flagged={newly_flagged} "
                        f"pending={gif_pending_count(chat_id)}"
                    )
                if newly_flagged:
                    async def gif_mute_succeeded(_result):
                        print("USER MUTED 3600")
                        notification_key = (chat_id, user_id)
                        now = _asyncio.get_running_loop().time()
                        notified_until = getattr(bot, "gif_spam_notification_until", {})
                        if notified_until.get(notification_key, 0) <= now:
                            if not hasattr(bot, "gif_spam_notification_until"):
                                bot.gif_spam_notification_until = {}
                            bot.gif_spam_notification_until[notification_key] = now + 3600
                            await _send_moderation_notification_once(
                                bot, chat_id, user_id, "gif_mute", event.message.id,
                                "🔹کاربر ← "
                                f"{_format_banned_user(sender, user_id)}\n\n"
                                "به دلیل ارسال گیف تکراری 𝟭 ساعت سکوت شد",
                            )
                            print("GIF WARNING SENT")

                    async def gif_mute_failed(_error):
                        reset_gif_history(chat_id, user_id)

                    bot.moderation_queue.enqueue(
                        chat_id,
                        "mute",
                        user_id=user_id,
                        timeout_seconds=15,
                        operation=lambda: bot.admin_actions.mute_user(chat_id, user_id, 3600),
                        on_success=gif_mute_succeeded,
                        on_failure=gif_mute_failed,
                    )
                    if deleted:
                        bot.logger.log_info(
                            f"consecutive GIF spam deleted chat_id={chat_id} user_id={user_id} count={deleted}"
                        )
                # هر GIF مشمول، چه در آستانه و چه پس از آن، همین‌جا پایان
                # می‌یابد و وارد فیلترهای دیگر نمی‌شود.
                if repeated_gif_ids:
                    return

        is_forwarded, forward_field, forward_fields = _get_forward_metadata(
            event.message
        )
        profiler.mark("FORWARD_CHECK")
        if is_forwarded:
            bot.logger.log_info(
                "FORWARD DETECTED "
                f"user_id={user_id} username={sender_username} "
                f"forward_field={forward_field} fields={forward_fields}"
            )
            if not is_group_moderator:
                deleted = False
                forward_key = (chat_id, user_id)
                forward_count = getattr(bot, "forward_spam_counts", {}).get(
                    forward_key, 0
                ) + 1
                bot.forward_spam_counts[forward_key] = forward_count
                try:
                    await bot.client.delete_messages(chat_id, [event.message.id])
                    deleted = True
                    if forward_count >= 3:
                        processing = getattr(bot, "forward_spam_processing", set())
                        if forward_key in processing:
                            return
                        if not hasattr(bot, "forward_spam_processing"):
                            bot.forward_spam_processing = set()
                        bot.forward_spam_processing.add(forward_key)
                        async def forward_mute_finished(_result):
                            try:
                                await _send_moderation_notification_once(
                                    bot, chat_id, user_id, "forward_spam_mute",
                                    event.message.id,
                                    "🔸کاربر ← "
                                    f"{_format_banned_user(sender, user_id)}\n\n"
                                    "به دلیل ارسال فوروارد تکراری 𝟮𝟰 ساعت سکوت شد",
                                )
                            finally:
                                bot.forward_spam_counts.pop(forward_key, None)
                                bot.forward_spam_processing.discard(forward_key)

                        async def forward_mute_failed(_error):
                            bot.forward_spam_counts.pop(forward_key, None)
                            bot.forward_spam_processing.discard(forward_key)

                        bot.moderation_queue.enqueue(
                            chat_id,
                            "mute",
                            user_id=user_id,
                            timeout_seconds=15,
                            operation=lambda: bot.admin_actions.mute_user(
                                chat_id, user_id, 24 * 60 * 60
                            ),
                            on_success=forward_mute_finished,
                            on_failure=forward_mute_failed,
                        )
                finally:
                    bot.logger.log_info(
                        "FORWARD DETECTED "
                        f"user_id={user_id} username={sender_username} "
                        f"forward_field={forward_field} deleted={deleted} "
                        f"forward_count={forward_count}"
                    )
                if name_family_trace:
                    bot.logger.log_info(
                        "NAME FAMILY TRACE HANDLER_BLOCK "
                        f"reason=forwarded_message chat_id={chat_id} user_id={user_id}"
                    )
                return

        burst_key = (chat_id, user_id)
        if burst_key in bot.spam_burst_users:
            _queue_spam_burst_deletion(
                bot, chat_id, user_id, {event.message.id}
            )
            if name_family_trace:
                bot.logger.log_info(
                    "NAME FAMILY TRACE HANDLER_BLOCK "
                    f"reason=spam_burst chat_id={chat_id} user_id={user_id}"
                )
            return

        if clean_text == "صفر":
            if not is_global_owner(getattr(sender, "id", None)):
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
            _log_command_route(bot, clean_text, "ثبت اصل", "user_original.set")
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

        if clean_text in INSULTS:
            await event.reply(INSULT_REPLY)
            return

        simple_reply = SIMPLE_REPLIES.get(clean_text)
        if simple_reply:
            await event.reply(simple_reply)
            return

        # بیوگرافی باید پیش از فیلتر گروهیِ کلمهٔ مستقل «بیو» اجرا شود.
        if clean_text == "بیوگرافی":
            await event.reply(get_biography(chat_id))
            return

        if clean_text == "یاد آوری":
            begin_reminder(chat_id, user_id, _format_admin_display(sender))
            await event.reply("📝 متن یادآوری و زمان موردنظر را ارسال کنید.")
            return

        if waiting_reminder(chat_id, user_id):
            reminder = capture_reminder(chat_id, user_id, message_text)
            if reminder is False:
                await event.reply("❌ زمان را مانند «۳۰ دقیقه آب بخور» ارسال کنید.")
            else:
                await event.reply(
                    "✅ یادآوری ثبت شد.\n\n"
                    f"⏰ زمان: {reminder['time_label']}\n"
                    f"📝 متن: {reminder['text']}"
                )
            return

        if clean_text == "ترجمه":
            begin_translation(chat_id, user_id)
            await event.reply("🌐 متن انگلیسی خود را ارسال کنید.")
            return

        if waiting_translation(chat_id, user_id):
            # ترجمه هم درخواست HTTP همگام است؛ خارج از حلقه اجرا می‌شود.
            translated, error = await _asyncio.to_thread(
                translate_to_persian, message_text)
            clear_translation(chat_id, user_id)
            if error:
                await event.reply(error)
            else:
                translation_text = (
                    "🌐 ترجمه\n\n"
                    f"🇬🇧 متن:\n\n{message_text}\n\n"
                    f"🇮🇷 ترجمه:\n\n{translated}"
                )
                def translation_u16(value):
                    return len(value.encode("utf-16-le")) // 2
                title = "🌐 ترجمه"
                source_title = "🇬🇧 متن:"
                target_title = "🇮🇷 ترجمه:"
                target_start = translation_text.rfind(translated)
                entities = []
                for label in (title, source_title, target_title):
                    pos = translation_text.index(label)
                    entities.append(MessageEntityBold(offset=translation_u16(translation_text[:pos]), length=translation_u16(label)))
                entities.append(MessageEntityBold(offset=translation_u16(translation_text[:target_start]), length=translation_u16(translated)))
                entities.append(MessageEntityBlockquote(offset=translation_u16(translation_text[:target_start]), length=translation_u16(translated)))
                await event.reply(translation_text, formatting_entities=entities)
            return

        # ضدتکرار فقط برای پیام‌های سریع و یکسانِ کاربران عادی اجرا می‌شود.
        if not fast_command and not is_group_moderator:
            try:
                if is_repeat(chat_id, user_id, message_text):
                    punish_key = f"{chat_id}:{user_id}"
                    _log_ban_execution(bot, chat_id, user_id, "اسپم تکراری")
                    if punish_key in bot.punished_users:
                        return
                    bot.punished_users.add(punish_key)
                    bot.spam_burst_users.add(punish_key)
                    ids = get_message_ids(chat_id, user_id)
                    async def repeat_history_ban_succeeded(_result):
                        _queue_spam_burst_deletion(bot, chat_id, user_id, set(ids))
                        await _send_moderation_notification_once(
                            bot, chat_id, user_id, "spam_ban", event.message.id,
                            "⚠️ کاربر ⏌ "
                            f"{_format_banned_user(sender, user_id)}"
                            " ⎾\n\nبه دلیل هرزنامه از گروه اخراج شد.",
                        )

                    async def repeat_history_ban_failed(_error):
                        bot.punished_users.discard(punish_key)
                        bot.spam_burst_users.discard(punish_key)

                    bot.moderation_queue.enqueue(
                        chat_id,
                        "ban",
                        user_id=user_id,
                        timeout_seconds=20,
                        operation=lambda: bot.admin_actions.ban_user(
                            chat_id, user_id, reason="اسپم تکراری"
                        ),
                        on_success=repeat_history_ban_succeeded,
                        on_failure=repeat_history_ban_failed,
                    )
                    if name_family_trace:
                        bot.logger.log_info(
                            "NAME FAMILY TRACE HANDLER_BLOCK "
                            f"reason=repeat_spam chat_id={chat_id} user_id={user_id}"
                        )
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

                # جستجو یک درخواست HTTP همگام با timeout تا ۲۰ ثانیه است.
                # اجرای مستقیم آن، حلقهٔ رویداد و در نتیجه همهٔ گروه‌ها را
                # تا پایان درخواست قفل می‌کرد.
                result = await _asyncio.to_thread(search_web, query)
                await event.reply(result)
                return


        # ---- 📥 دانلود عکس (مستقل، قبل از بازی‌ها) ----
        if await handle_photo_download(
            bot, event, chat_id, user_id, sender, clean_text, bot.logger
        ):
            return

        # ---- بازی‌های Fox AI (کاملاً مستقل، فقط از این نقطه وصل می‌شوند) ----
        if await handle_fox_games(
            bot, event, chat_id, user_id, sender, clean_text, bot.logger
        ):
            return

        # بازی اسم فامیل
        if clean_text == "اسم فامیل":
            if _chat_game_busy(chat_id):
                await event.reply(GAME_BUSY_MESSAGE)
                return
            game = start_name_family(chat_id)
            await event.reply(
                "🎮 اسم فامیل\n\n"
                f"حرف: {game['letter']}\n\n"
                "⏳ زمان: 90 ثانیه\n\n"
                "👤 نام\n👤 فامیل\n🌍 شهر\n🍇 میوه\n📦 وسیله\n🐶 حیوان\n🎵 خواننده"
            )
            async def name_family_results(ranking):
                """نمایش نتایج؛ توسط مسیر اختصاصی همین بازی فراخوانی می‌شود."""
                if not ranking:
                    await event.reply("🏆 نتایج\n\nشرکت‌کننده‌ای پاسخ صحیح ثبت نکرد.")
                    return
                medals = ("🥇", "🥈", "🥉")
                lines = ["🏆 نتایج\n"]
                for index, player in enumerate(ranking, 1):
                    medal = medals[index - 1] if index <= 3 else "•"
                    reward = ""
                    if player["points"] >= 70:
                        try:
                            economy.award_game(
                                chat_id, player.get("user_id", "unknown"),
                                "name_family",
                                reference=f"namefamily:{chat_id}:"
                                          f"{game['round_id']}:"
                                          f"{player.get('user_id')}",
                                name=player["name"],
                            )
                            reward = (
                                " — 🪙 +"
                                f"{_math_digits(economy.rewards.amount_for('name_family'))}"
                                " سکه "
                                f"{economy.rewards.coin_name(economy.rewards.coin_for('name_family'))}"
                            )
                        except Exception as error:
                            # پاداش نباید مانع نمایش نتایج شود.
                            bot.logger.log_error(
                                f"NAME FAMILY REWARD FAILED chat_id={chat_id} "
                                f"player={player['name']} error={error!r}"
                            )
                    lines.append(f"{medal} {player['name']} — {player['points']} امتیاز{reward}")
                await event.reply("\n".join(lines))

            # تایمر این بازی در صف اختصاصی خودش نگه داشته می‌شود، نه در
            # group_timer_tasks مشترک؛ پس هیچ بازی یا دستور دیگری نمی‌تواند
            # آن را لغو کند و نتایج همیشه ارسال می‌شوند.
            schedule_name_family_round(
                chat_id,
                game["round_id"],
                name_family_results,
                logger=bot.logger,
            )
            bot.logger.log_info(
                "NAME FAMILY ROUND STARTED "
                f"chat_id={chat_id} round_id={game['round_id']} "
                f"letter={game['letter']} seconds={game.get('seconds', 90)}"
            )
            return

        # ثبت پاسخ اسم فامیل در همان بازی فعال
        if name_family_active(chat_id):
            bot.logger.log_info(
                "NAME FAMILY TRACE HANDLER_BEFORE_SUBMIT "
                f"chat_id={chat_id} user_id={user_id} "
                f"line_count={len(clean_text.splitlines())} char_count={len(clean_text)}"
            )
            # هر ثبت اسم فامیل ممکن است تا ۷ جستجوی وب همگام انجام دهد
            # (هر دسته یک بار، هرکدام تا ۲ ثانیه). اجرای مستقیم آن حلقه را
            # ده‌ها ثانیه قفل می‌کرد و همهٔ گروه‌ها بی‌پاسخ می‌ماندند.
            submitted = await _asyncio.to_thread(
                submit_name_family,
                chat_id,
                user_id,
                _format_group_member(sender),
                clean_text,
                logger=bot.logger,
                learning_min_observations=bot.config_manager.get("name_family_learning_min_observations", 5),
                learning_min_unique_users=bot.config_manager.get("name_family_learning_min_unique_users", 3),
                learning_min_unique_chats=bot.config_manager.get("name_family_learning_min_unique_chats", 2),
            )
            bot.logger.log_info(
                "NAME FAMILY TRACE HANDLER_AFTER_SUBMIT "
                f"chat_id={chat_id} user_id={user_id} submitted={submitted!r}"
            )
            if submitted is not None:
                await event.reply("✅ پاسخ ثبت شد")
                return

        # ریست پیشرفت حدس ایموجی — تنها راه پاک کردن پیشرفت.
        # ری‌استارت ربات هرگز پیشرفت را پاک نمی‌کند.
        if clean_text in EMOJI_RESET_COMMANDS:
            emoji_guess_reset(chat_id, user_id)
            await event.reply(
                "🔄 پیشرفت حدس ایموجی شما در این گروه پاک شد.\n\n"
                "با «حدس ایموجی» از مرحله ۱ شروع کنید."
            )
            return

        # بازی حدس ایموجی
        if clean_text == "حدس ایموجی":
            if _chat_game_busy(chat_id):
                await event.reply(GAME_BUSY_MESSAGE)
                return
            # معمای باز خودِ کاربر نباید با دستور دوباره بازنویسی شود.
            if emoji_guess_active(chat_id, user_id):
                await event.reply(
                    "⏳ شما یک معمای باز دارید؛ اول همان را پاسخ دهید."
                )
                return
            # تاریخچه به تفکیک کاربر: هیچ معمای تکراری برای همان کاربر
            # ارسال نمی‌شود. وقتی همهٔ مرحله‌ها مصرف شد، خودِ start یک
            # «دور» تازه می‌سازد، پس اینجا دیگر جلوی کاربر گرفته نمی‌شود.
            puzzle = start_emoji_guess(chat_id, user_id)
            if puzzle is None:
                await event.reply(EMOJI_GUESS_EXHAUSTED_MESSAGE)
                return
            await event.reply(
                "🎮 حدس ایموجی\n\n"
                f"مرحله {_math_digits(puzzle['stage'])} از "
                f"{_math_digits(EMOJI_GUESS_TOTAL)} — سطح {puzzle['tier']}\n\n"
                f"{puzzle['emoji']}\n\n"
                f"⏳ {_math_digits(EMOJI_GUESS_SECONDS)} ثانیه فرصت دارید"
            )

            async def emoji_timer():
                await _asyncio.sleep(EMOJI_GUESS_SECONDS)
                answer = finish_emoji_guess(
                    chat_id, puzzle["token"], user_id)
                if answer:
                    await event.reply(f"⏰ زمان تمام شد!\n\n✅ پاسخ درست:\n{answer}")
            _track_group_timer(bot, chat_id, _asyncio.create_task(emoji_timer()))
            return

        if emoji_guess_active(chat_id, user_id):
            emoji_token = puzzle_token_for(chat_id, user_id)
            winner_answer = answer_emoji_guess(chat_id, user_id, _format_group_member(sender), clean_text)
            if winner_answer:
                # سکه را خودِ ماژول از راه API اقتصاد پرداخت کرده است؛
                # اینجا فقط موجودی تازه از دیتابیس خوانده و اعلام می‌شود
                # تا دوبار پرداخت نشود.
                balance = economy.get_balance(chat_id, user_id)
                await event.reply(
                    "🎉 پاسخ صحیح بود.\n\n"
                    f"🪙 شما +{_math_digits(EMOJI_REWARD_BRONZE)} سکه برنز دریافت کردید.\n\n"
                    f"💰 موجودی برنز:\n🥉 {_math_digits(balance[economy.BRONZE])}\n\n"
                    f"💎 ارزش کل:\n{_math_digits(balance['total_coin_value'])}"
                )
                return

        # بازی حدس پرچم؛ پرچم Unicode برای نمایش پایدار در Soroush Plus استفاده می‌شود.
        if clean_text == "حدس پرچم":
            if _chat_game_busy(chat_id):
                await event.reply(GAME_BUSY_MESSAGE)
                return
            # محدودیت به تفکیک کاربر: وقتی کاربری همهٔ پرچم‌ها را دید، بازی
            # برای او بسته می‌شود تا امتیاز تکراری نگیرد. سایر کاربران آزادند.
            if flag_guess_exhausted(user_id):
                await event.reply(FLAG_GUESS_EXHAUSTED_MESSAGE)
                return
            flag_game = start_flag_guess(chat_id, user_id)
            if flag_game is None:
                await event.reply(FLAG_GUESS_EXHAUSTED_MESSAGE)
                return
            await event.reply(
                "🌍 حدس پرچم\n\n"
                f"{flag_game['flag']}\n\n"
                "این پرچم متعلق به کدام کشور است؟\n\n"
                "⏳ زمان: 30 ثانیه"
            )

            async def flag_timer():
                await _asyncio.sleep(30)
                answer = finish_flag_guess(chat_id, flag_game["token"])
                if answer:
                    await event.reply(f"⏰ زمان تمام شد!\n\n✅ پاسخ درست: {answer}")

            _track_group_timer(bot, chat_id, _asyncio.create_task(flag_timer()))
            return

        if flag_guess_active(chat_id):
            # ⚠️ token باید *پیش* از answer() خوانده شود؛ answer() جلسه را
            # می‌بندد. پیش‌تر اینجا از متغیر flag_game استفاده می‌شد که فقط
            # در شاخهٔ «شروع» ساخته می‌شد، پس در پیام پاسخ اصلاً وجود نداشت
            # و UnboundLocalError می‌داد: کاربر پیام «+۳ سکه» می‌دید ولی
            # هیچ سکه‌ای دریافت نمی‌کرد.
            flag_state = get_flag_guess(chat_id)
            flag_token = flag_state["token"] if flag_state else 0
            country = answer_flag_guess(chat_id, clean_text, user_id)
            if country:
                await _reward_game_reply(
                    event, chat_id, user_id, sender, "flag",
                    reference=f"flag:{chat_id}:{user_id}:{flag_token}",
                )
                return

        # بازی تصحیح کلمات
        if clean_text == "تصحیح کلمات":
            if _chat_game_busy(chat_id):
                await event.reply(GAME_BUSY_MESSAGE)
                return
            game = start_correction(chat_id)
            await event.reply(f"{game['wrong']}\n\n۳۰ ثانیه زمان دارید صحیح کلمه را بنویسید")
            async def correction_timer():
                await _asyncio.sleep(30)
                active = get_correction(chat_id)
                if active and active['token'] == game['token']:
                    clear_correction(chat_id, game['token'])
                    await event.reply(f"پاسخ درست:\n{active['correct']}")
            _track_group_timer(bot, chat_id, _asyncio.create_task(correction_timer()))
            return

        correction_state = get_correction(chat_id)
        result_correction = answer_correction(chat_id, clean_text)
        if result_correction is not None:
            if result_correction:
                await _reward_game_reply(
                    event, chat_id, user_id, sender, "correction",
                    reference=f"correction:{chat_id}:"
                              f"{correction_state['token'] if correction_state else 0}",
                )
            return

        # بازی چهار گزینه‌ای
        normalized_game_command = " ".join(
            clean_text.replace("‌", " ").split()
        )
        if normalized_game_command == "چهار گزینه ای":
            if _chat_game_busy(chat_id):
                await event.reply(GAME_BUSY_MESSAGE)
                return
            try:
                # ⚠️ اینجا عمداً گیتِ «تمام شد» وجود ندارد.
                #
                # پیش‌تر اگر کاربر همهٔ سوال‌ها را دیده بود، بازی برای
                # همیشه برایش بسته می‌شد. حالا ``start_question`` خودش
                # دور تازه می‌سازد و سوال‌هایی که دیرتر دیده شده‌اند
                # دوباره وارد چرخه می‌شوند. ``None`` فقط یعنی واقعاً
                # هیچ سوالی در بانک نیست.
                quiz = start_question(chat_id, user_id)
                if quiz is None:
                    await event.reply(QUIZ_EXHAUSTED_MESSAGE)
                    return
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
                    await _asyncio.sleep(QUIZ_SECONDS)
                    active_quiz = get_active_question(chat_id)
                    if active_quiz and active_quiz["token"] == quiz["token"]:
                        clear_question(chat_id, quiz["token"])
                        await event.reply(
                            "⏰ زمان تمام شد!\n\n"
                            f"پاسخ درست:\nگزینه {active_quiz['answer']}"
                        )

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
                fill_token = get_fill_token(chat_id, user_id)
                await event.reply(
                    "📝 جای خالی:\n\n" + q
                    + f"\n\n⏳ {_math_digits(FILL_TIMEOUT)} ثانیه فرصت داری"
                )

                async def fill_timer():
                    # مهلت تایمر دقیقاً برابر مهلت پذیرش پاسخ است و پاک‌سازی
                    # با توکن انجام می‌شود، پس تایمر دور قبلی نمی‌تواند پاسخ
                    # دور جدید را لو بدهد.
                    await _asyncio.sleep(FILL_TIMEOUT)
                    ans = clear_fill(chat_id, user_id, fill_token)
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
                riddle_token = get_riddle_token(chat_id, user_id)
                await event.reply(
                    "🧩 چیستان:\n\n" + q
                    + f"\n\n⏳ {_math_digits(RIDDLE_TIMEOUT)} ثانیه فرصت داری جواب بده"
                )

                async def riddle_timer():
                    # قبلاً تایمر ۶۰ ثانیه بود ولی پذیرش پاسخ ۵۰ ثانیه؛ یعنی
                    # ۱۰ ثانیه کاربر پاسخ درست می‌داد و هیچ اتفاقی نمی‌افتاد.
                    await _asyncio.sleep(RIDDLE_TIMEOUT)
                    answer = clear_riddle(chat_id, user_id, riddle_token)
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
            fill_state = get_fill_token(chat_id, user_id)
            if check_fill(chat_id, user_id, clean_text):
                # پیش‌تر این بازی هیچ جایزه‌ای نمی‌داد.
                await _reward_game_reply(
                    event, chat_id, user_id, sender, "fill_blank",
                    reference=f"fill:{chat_id}:{user_id}:{fill_state}",
                )
                return
        except Exception as e:
            bot.logger.log_error(f"خطای جای خالی: {e}")

        try:
            riddle_answer_token = get_riddle_token(chat_id, user_id)
            if check_answer(chat_id, user_id, clean_text):
                await _reward_game_reply(
                    event, chat_id, user_id, sender, "riddle",
                    reference=f"riddle:{chat_id}:{user_id}:{riddle_answer_token}",
                )
                return
        except Exception as e:
            bot.logger.log_error(f"خطای بررسی جواب چیستان: {e}")

        try:
            quiz_state = get_active_question(chat_id)
            result = answer_question(chat_id, clean_text, user_id)
            if result is not None:
                is_correct, correct_option = result
                if is_correct:
                    await _reward_game_reply(
                        event, chat_id, user_id, sender, "quiz",
                        reference=f"quiz:{chat_id}:"
                                  f"{quiz_state['token'] if quiz_state else 0}",
                    )
                else:
                    await event.reply(
                        f"❌ غلط بود. گزینه {correct_option} درست بود."
                    )
                return
        except Exception as e:
            bot.logger.log_error(f"خطای بررسی پاسخ چهار گزینه‌ای: {e}")

# ثبت آمار پیام گروه
        try:
            if not event.is_private and not fast_command:
                # sender/chat در ابتدای handler resolve شده‌اند؛ دوباره API نخوان.
                _run_background(
                    bot,
                    "group_stats",
                    add_message,
                    chat_id,
                    user_id,
                    getattr(sender, "username", "") or "",
                )
                record_coin_message(
                    chat_id, user_id, _format_admin_display(sender),
                )

        except Exception as e:
            bot.logger.log_error(
                f"خطای ثبت آمار پیام: {e}"
            )

        # اتصال دستورات فیلتر کلمات گروه
        try:
            # از sender/chat resolve‌شده در ابتدای handler استفاده می‌کنیم.
            handled_group_word = (
                not fast_command and await bot.check_group_word_commands(
                    event, clean_text, chat_id, user_id
                )
            )
            if handled_group_word:
                return

        except Exception as e:
            bot.logger.log_error(
                f"خطای فیلتر گروه: {e}"
            )

        # بازی جرعت حقیقت
        clean_text = message_text.strip()

        if clean_text in ["جرعت", "جرات", "جرئت"]:
            await event.reply("🎯 جرعت:\n" + get_jorat(chat_id))
            return

        if clean_text in ["حقیقت", "حقیقت بگو"]:
            await event.reply("🧠 حقیقت:\n" + get_haghighat(chat_id))
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
            await event.reply(get_joke(chat_id))
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
                "🎮 لیست بازی‌های روباه\n\n"
                "🧩 چیستان\n"
                "معماهای متنوع برای افزایش هوش و دقت.\n\n"
                "😀 حدس ایموجی\n"
                "حدس عبارت یا کلمه از روی ایموجی‌ها.\n\n"
                "🌍 حدس پرچم\n"
                "تشخیص کشورها از روی پرچم‌های ایموجی.\n\n"
                "📝 اسم فامیل\n"
                "رقابت گروهی با امتیازدهی خودکار.\n\n"
                "✍️ تصحیح کلمات\n"
                "پیدا کردن شکل صحیح کلمات.\n\n"
                "❓ چهار گزینه‌ای\n"
                "پاسخ به سوالات چهارگزینه‌ای در موضوعات مختلف.\n\n"
                "📝 جای خالی\n"
                "تکمیل جمله‌ها و سوالات متنوع.\n\n"
                "😂 بخند یا بباز\n"
                "اولین نفری که ایموجی خنده ارسال کند برنده می‌شود.\n\n"
                "🏕 بقا\n"
                "مرحله‌به‌مرحله به سوالات پاسخ بده و تا پایان بازی زنده بمان.\n\n"
                "🎁 جعبه شانسی\n"
                "از بین ۹ جعبه یکی را انتخاب کن و جایزه یا پوچ بگیر.\n\n"
                "🧛 خون‌آشام\n"
                "خون‌آشام مخفی را قبل از تمام شدن زمان پیدا کن و جایزه بگیر.\n\n"
                "🧩 معما\n"
                "هر بار با ارسال «معما» یک معمای فکری پرسیده می‌شود؛ بعد از پاسخ صحیح یا پایان زمان، بازی تمام می‌شود.\n\n"
                "🎯 بهترین جواب\n"
                "به فکری‌ترین و دقیق‌ترین پاسخ برس و جایزه بگیر.\n\n"
                "⚔️ نبرد\n"
                "رقابت دو نفره با سوالات سخت، علمی و فکری.\n\n"
                "🎭 جرأت حقیقت\n"
                "با ارسال «جرعت» یا «حقیقت»، یک جرأت یا سوال صادقانه دریافت کن.\n\n"
                "😄 جک\n"
                "با ارسال «جک»، یک جوک یا لطیفه خنده‌دار دریافت کن."
            )

            entities = []

            def u16(x):
                return len(x.encode("utf-16-le")) // 2

            for word in [
                "🎮 لیست بازی‌های روباه",
                "🧩 چیستان",
                "😀 حدس ایموجی",
                "🌍 حدس پرچم",
                "📝 اسم فامیل",
                "✍️ تصحیح کلمات",
                "❓ چهار گزینه‌ای",
                "📝 جای خالی",
                "😂 بخند یا بباز",
                "🏕 بقا",
                "🎁 جعبه شانسی",
                "🧛 خون‌آشام",
                "🧩 معما",
                "🎯 بهترین جواب",
                "⚔️ نبرد",
                "🎭 جرأت حقیقت",
                "با ارسال «جرعت» یا «حقیقت»، یک جرأت یا سوال صادقانه دریافت کن.",
                "😄 جک",
                "با ارسال «جک»، یک جوک یا لطیفه خنده‌دار دریافت کن.",
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
        help_commands = {"راهنما", "/help", "!help", "help", "لیست کاربران", "لیست ادمینی"}
        if clean_text.strip() in help_commands:
            # متن راهنما برای همهٔ کاربران یکسان است؛ هیچ نام یا اطلاعات
            # شخصی‌ای داخل آن قرار نمی‌گیرد. دستور «شخصیت» منطق جداگانهٔ
            # خودش را دارد و فقط نامی را تحلیل می‌کند که کاربر خودش می‌نویسد.
            full_help_text = (
                "📌 راهنمای روباه\n\n"

                "👤 کاربران:\n\n"
                "برای ثبت اصل بنویسید:\n"
                "ثبت اصل\n\n"
                "برای نمایش اصل بنویسید:\n"
                "اصلم\n\n"
                "آمار یک کاربر:\n"
                "برای دریافت آمار بنویسید:\n"
                "آمارم\n\n"
                "برای گرفتن بیوگرافی:\n"
                "بیوگرافی\n\n"

                "🎮 لیست بازی‌ها:\n\n"
                "برای مشاهده بازی‌ها بنویسید:\n"
                "لیست بازی\n\n"

                "🧩 معما:\n"
                "با ارسال «معما» یک معما از روی ایموجی‌ها شروع می‌شود.\n"
                "فقط خودت می‌توانی پاسخ دهی. زمان: ۴۰ ثانیه.\n"
                "پاسخ صحیح: ۳ سکه برنز.\n\n"
                "🎯 بهترین جواب:\n"
                "با ارسال «بهترین جواب» یک سوال فکری مطرح می‌شود.\n"
                "پاسخ خود را بفرستید؛ بهترین پاسخ برنده است. زمان: ۴۰ ثانیه.\n"
                "جایزه بهترین پاسخ: ۲ سکه برنز.\n\n"
                "⚔️ نبرد:\n"
                "با «نبرد» شروع و بازیکن دوم با «شرکت» می‌پیوندد.\n"
                "هر بازیکن ۳ سوال سخت می‌گیرد؛ هر کدام ۳۰ ثانیه.\nبرنده: ۲ سکه برنز (اگر مساوی شود هر دو ۲ سکه برنز).\n\n"
                "🎭 جرأت حقیقت:\n"
                "با ارسال «جرعت» یا «حقیقت»، یک جرأت یا سوال صادقانه دریافت کن.\n\n"
                "😄 جک:\n"
                "با ارسال «جک»، یک جوک یا لطیفه خنده‌دار دریافت کن.\n\n"

                "🎵 جستجوی آهنگ و مطالب:\n\n"
                "برای جستجو بنویسید:\n"
                "جستجو دانلود اسم آهنگ\n\n"
                "برای جستجو مطالب بنویسید:\n"
                "جستجو اسم مطلبی که می‌خواهید بدانید\n\n"

                "✍️ ساخت فونت:\n\n"
                "فونت متن شما\n\n"

                "🌐 ترجمه انگلیسی به فارسی:\n\n"
                "برای استفاده بنویسید:\n"
                "ترجمه\n\n"

                "🏆 امتیاز و رتبه:\n\n"
                "برای دریافت راهنمای امتیاز:\n"
                "راهنمای امتیاز\n\n"
                "برای نمایش امتیاز خود:\n"
                "امتیاز من\n\n"
                "برای مشاهده برترین کاربران گروه:\n"
                "رتبه ها\n\n"

                "⏰ یادآوری:\n\n"
                "برای ثبت یادآوری:\n"
                "یاد آوری\n\n"

                "🧠 حافظه گروه:\n\n"
                "حافظه گروه بعد از ثبت اسم، ربات شما را با اسم صدا می‌کند.\n\n"
                "ثبت اسم:\n"
                "ثبت اسم علی\n"
                "یا\n"
                "ثبت علی\n\n"
                "مشاهده حافظه:\n"
                "حافظه من\n\n"
                "حذف اسم:\n"
                "حذف اسم\n\n"

                "🧩 تحلیل نام:\n\n"
                "شخصیت اسم خودتو بنویس\n\n"

                "📚 دانستنی:\n\n"
                "برای دریافت یک دانستنی:\n"
                "دانستنی\n\n"

                "🛒 اقتصاد و آیتم‌ها:\n\n"
                "برای دیدن لیست خرید و آیتم‌ها بنویسید:\n"
                "فروشگاه\n\n"
                "برای انتقال سکه، تبدیل سکه‌ها و مشاهده امکانات مالی بنویسید:\n"
                "موجودی\n\n"
                "برای ثبت و مدیریت پروفایل خود بنویسید:\n"
                "ثبت پرفایل | پرفایلم | حذف پرفایل\n\n"

                "🛡️ امنیت گروه:\n\n"
                "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\n\n"

                "👑 دستورات ادمین‌ها:\n\n"
                "دیدن لیست ادمین‌ها\n"
                "بنویسید:\n"
                "لیست ادمین\n\n"
                "برای قفل کردن ارسال پیام گروه:\nقفل\n\n"
                "برای باز کردن ارسال پیام در گروه بنویسید:\nباز\n\n"
                "برای خالی کردن لیست اخراج شده ها:\nریست اخراجی ها\n\n"
                "📜 قوانین گروه (مدیر)\n"
                "ثبت قوانین  |  قوانین  |  حذف قوانین\n\n"
                "برای حذف حافظهٔ یک کاربر روی پیام او ریپلای کنید و بنویسید:\n\n"
                "روی کاربر ریپلای کنید بنویسید: حذف حافظه\n\n"
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
                "برای سنجاق کردن پیام\n"
                "روی پیام موردنظر ریپلای کنید و بنویسید:\n"
                "سنجاق\n\n"
                "برای نمایش پیام سنجاق‌شده\n"
                "بنویسید:\n"
                "پیام سنجاق\n\n"
                "⚠️ صفر کردن تخلفات:\n"
                "با سازنده ربات تماس بگیرید:\n"
                "@osine1"
            )

            admin_marker = "👑 دستورات ادمین‌ها:\n\n"
            games_marker = "🎮 لیست بازی‌ها:\n\n"
            if clean_text.strip() == "لیست کاربران":
                # «لیست کاربران» فقط دستورات کاربری را نشان می‌دهد؛ بخش بازی‌ها
                # از آن حذف می‌شود تا بازی‌ها فقط در «🎮 لیست بازی‌ها» دیده شوند.
                pre_admin = full_help_text[:full_help_text.index(admin_marker)]
                if games_marker in pre_admin:
                    gs = pre_admin.index(games_marker)
                    # پایان بخش بازی‌ها = شروع «جستجوی آهنگ»
                    ge = pre_admin.index("🎵 جستجوی آهنگ و مطالب:")
                    # بخش «🎮 لیست بازی‌ها» را نگه می‌داریم ولی فقط تا قبل از
                    # اولین بازی؛ تا کاربر بداند برای دیدن بازی‌ها «لیست بازی»
                    # بنویسد، بدون اینکه تک‌تک بازی‌ها در «لیست کاربران» بیایند.
                    first_game = pre_admin.find("🧩 معما:", gs)
                    games_intro = pre_admin[gs:first_game] if first_game != -1 \
                        else pre_admin[gs:ge]
                    help_text = pre_admin[:gs] + games_intro + pre_admin[ge:]
                else:
                    help_text = pre_admin
            elif clean_text.strip() == "لیست ادمینی":
                help_text = full_help_text[full_help_text.index(admin_marker):]
            else:
                help_text = (
                    "🦊 راهنمای روباه\n\n"
                    "برای دریافت دستورات عمومی و کاربران بنویسید:\n\n"
                    "لیست کاربران\n\n"
                    "برای دریافت دستورات مالک و ادمین‌ها بنویسید:\n\n"
                    "لیست ادمینی"
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

            # فقط عنوان‌ها و جمله‌های توضیحی Bold می‌شوند؛ دستورهایی که
            # کاربر باید بفرستد عمداً عادی می‌مانند تا قابل تشخیص باشند.
            # Bold با entity داخلی سروش پلاس ساخته می‌شود، نه Markdown.
            bold_pieces = [
                # عنوان بخش‌ها
                "👤 کاربران:",
                "🎮 لیست بازی‌ها:",
                "🎵 جستجوی آهنگ و مطالب:",
                "✍️ ساخت فونت:",
                "🌐 ترجمه انگلیسی به فارسی:",
                "🏆 امتیاز و رتبه:",
                "⏰ یادآوری:",
                "🧠 حافظه گروه:",
                "🧩 تحلیل نام:",
                "📚 دانستنی:",
                "🛒 اقتصاد و آیتم‌ها:",
                "🛡️ امنیت گروه:",
                # جمله‌های توضیحی
                "برای ثبت اصل بنویسید:",
                "برای نمایش اصل بنویسید:",
                "آمار یک کاربر:",
                "برای دریافت آمار بنویسید:",
                "برای گرفتن بیوگرافی:",
                "برای مشاهده بازی‌ها بنویسید:",
                "🧩 معما:\nبا ارسال «معما» یک معما از روی ایموجی‌ها شروع می‌شود.\nفقط خودت می‌توانی پاسخ دهی. زمان: ۴۰ ثانیه.\nپاسخ صحیح: ۳ سکه برنز.",
                "🎯 بهترین جواب:\nبا ارسال «بهترین جواب» یک سوال فکری مطرح می‌شود.\nپاسخ خود را بفرستید؛ بهترین پاسخ برنده است. زمان: ۴۰ ثانیه.\nجایزه بهترین پاسخ: ۲ سکه برنز.",
                "⚔️ نبرد:\nبا «نبرد» شروع و بازیکن دوم با «شرکت» می‌پیوندد.\nسوالات سخت، هر کدام ۳۰ ثانیه.\nبرنده: ۲ سکه برنز (اگر مساوی شود هر دو ۲ سکه برنز).",
                "🎭 جرأت حقیقت:\nبا ارسال «جرعت» یا «حقیقت»، یک جرأت یا سوال صادقانه دریافت کن.",
                "😄 جک:\nبا ارسال «جک»، یک جوک یا لطیفه خنده‌دار دریافت کن.",
                "برای جستجو بنویسید:",
                "برای جستجو مطالب بنویسید:",
                "برای استفاده بنویسید:",
                "برای دریافت راهنمای امتیاز:",
                "برای نمایش امتیاز خود:",
                "برای مشاهده برترین کاربران گروه:",
                "برای ثبت یادآوری:",
                "حافظه گروه بعد از ثبت اسم، ربات شما را با اسم صدا می‌کند.",
                "ثبت اسم:",
                "مشاهده حافظه:",
                "حذف اسم:",
                "برای دریافت یک دانستنی:",
                "برای دیدن لیست خرید و آیتم‌ها بنویسید:",
                "برای انتقال سکه، تبدیل سکه‌ها و مشاهده امکانات مالی بنویسید:",
                "برای ثبت و مدیریت پروفایل خود بنویسید:",
                "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.",
                # منوی کوتاه
                "برای دریافت دستورات عمومی و کاربران بنویسید:",
                "برای دریافت دستورات مالک و ادمین‌ها بنویسید:",
                # بخش ادمین (دست‌نخورده)
                "👑 دستورات ادمین‌ها:",
                "دیدن لیست ادمین‌ها",
                "برای سنجاق کردن پیام",
                "برای نمایش پیام سنجاق‌شده",
                "برای قفل کردن ارسال پیام گروه:",
                "برای باز کردن ارسال پیام در گروه بنویسید:",
                "📜 قوانین گروه (مدیر)",
                "برای حذف حافظهٔ یک کاربر روی پیام او ریپلای کنید و بنویسید:",
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
                "⚠️ اخطار دادن به کاربر:",
                "⚠️ صفر کردن تخلفات:",
            ]
            # هر تکه ممکن است چند بار در متن بیاید (مثل «حذف اسم:» که هم
            # عنوان است هم دستور)؛ فقط جایگاه‌های واقعی علامت می‌خورند.
            for word in bold_pieces:
                search_from = 0
                while True:
                    pos = help_text.find(word, search_from)
                    if pos == -1:
                        break
                    entities.append(
                        MessageEntityBold(
                            offset=u16(help_text[:pos]),
                            length=u16(word)
                        )
                    )
                    search_from = pos + len(word)

            admin_command_quotes = (
                ("دیدن لیست ادمین‌ها\nبنویسید:\nلیست ادمین", "لیست ادمین"),
                ("برای سنجاق کردن پیام\nروی پیام موردنظر ریپلای کنید و بنویسید:\nسنجاق", "سنجاق"),
                ("برای نمایش پیام سنجاق‌شده\nبنویسید:\nپیام سنجاق", "پیام سنجاق"),
                ("برای قفل کردن ارسال پیام گروه:\nقفل", "قفل"),
                ("برای باز کردن ارسال پیام در گروه بنویسید:\nباز", "باز"),
                ("برای خالی کردن لیست اخراج شده ها:\nریست اخراجی ها", None),
            )
            for section, command in admin_command_quotes:
                section_start = help_text.find(section)
                if section_start == -1:
                    continue
                command_start = section_start
                command_length = len(section)
                if command is not None:
                    command_start += section.rfind(command)
                    command_length = len(command)
                entities.append(
                    MessageEntityBlockquote(
                        offset=u16(help_text[:command_start]),
                        length=u16(help_text[command_start:command_start + command_length]),
                    )
                )

            quote_sections = [
                "لیست کاربران",
                "لیست ادمینی",
                # کل بخش قوانین گروه باید یک نقل قول شیشه‌ای یکپارچه باشد.
                "📜 قوانین گروه (مدیر)\n"
                "ثبت قوانین  |  قوانین  |  حذف قوانین\n\n"
                "برای حذف حافظهٔ یک کاربر روی پیام او ریپلای کنید و بنویسید:\n\n"
                "روی کاربر ریپلای کنید بنویسید: حذف حافظه",
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
                if not is_global_owner(getattr(sender, "id", None)):
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

        if (
            clean_text.startswith(("!", "/", "."))
            and not clean_text.startswith(("/فیلتر ", "/رفع "))
            and clean_text != "/فیلترها"
        ):
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

        if clean_text == "ریست اخراجی ها":
            if str(user_id) != str(get_group_owner(chat_id)):
                await event.reply("❌ فقط مالک ثبت‌شده اجازه استفاده از این دستور را دارد")
                return

            banned_data = load_banned()
            group_key = str(chat_id)
            removed_count, remaining_entries = await reset_system_removed_users(
                bot.client,
                chat_id,
                banned_data.get(group_key, []),
                bot.logger,
            )
            if remaining_entries:
                banned_data[group_key] = remaining_entries
            else:
                banned_data.pop(group_key, None)
            save_banned(banned_data)
            await event.reply(f"🔗[ {removed_count} کاربران اخراج شده ] از لیست خارج شد")
            return

        if clean_text == "لیست ادمین":
            _log_command_route(bot, clean_text, "لیست ادمین", "admin_list")
            if not _has_group_management_permission(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply("❌ فقط مالک یا ادمین ثبت‌شده اجازه استفاده دارد")
                return

            async def admin_display(user_id=None, username=None):
                if username:
                    return f"@{username.lstrip('@')}"
                if user_id is not None:
                    try:
                        entity = await bot.client.get_entity(user_id)
                        return _format_admin_display(entity)
                    except Exception:
                        pass
                return "Unknown User"

            # بخش اول فقط از storage پایدار ادمین‌های ثبت‌شده توسط ربات.
            registered_entries = load_admins().get(normalize_group_id(chat_id), [])
            registered_admins = []
            for entry in registered_entries:
                if isinstance(entry, dict):
                    formatted = await admin_display(
                        user_id=entry.get("user_id"), username=entry.get("username")
                    )
                else:
                    formatted = await admin_display(username=entry)
                if formatted != "Unknown User":
                    registered_admins.append(formatted)

            # بخش دوم فقط از API ادمین‌های واقعی همین گروه.
            group_admins = []
            try:
                async for participant in bot.client.iter_participants(
                    chat_id, filter=types.ChannelParticipantsAdmins()
                ):
                    formatted = _format_admin_display(participant)
                    if formatted != "Unknown User":
                        group_admins.append(formatted)
            except Exception as error:
                bot.logger.log_error(f"خطا در دریافت ادمین‌های گروه: {error}")

            registered_text = "\n".join(
                f"★ : {admin}" for admin in registered_admins
            ) if registered_admins else "ندارد"
            group_text = "\n".join(
                f"☆ : {admin}" for admin in group_admins
            ) if group_admins else "ندارد"
            admin_text = (
                "✍ ادمین‌های ثبت‌شده ربات\n"
                f"{registered_text}\n\n"
                "✍ ادمین‌های گروه\n"
                f"{group_text}"
            )

            def admin_u16(value):
                return len(value.encode("utf-16-le")) // 2

            registered_title = "✍ ادمین‌های ثبت‌شده ربات"
            group_title = "✍ ادمین‌های گروه"
            registered_start = len(registered_title) + 1
            group_start = admin_text.index(group_title) + len(group_title) + 1
            entities = [
                MessageEntityBold(offset=0, length=admin_u16(registered_title)),
                MessageEntityBlockquote(
                    offset=admin_u16(admin_text[:registered_start]),
                    length=admin_u16(registered_text),
                ),
                MessageEntityBold(
                    offset=admin_u16(admin_text[:admin_text.index(group_title)]),
                    length=admin_u16(group_title),
                ),
                MessageEntityBlockquote(
                    offset=admin_u16(admin_text[:group_start]),
                    length=admin_u16(group_text),
                ),
            ]
            await event.reply(admin_text, formatting_entities=entities)
            return

        if clean_text == "سنجاق":
            if not _has_group_management_permission(bot, chat_id, user_id, getattr(sender, "username", None)):
                await event.reply("❌ فقط مالک یا ادمین ثبت‌شده اجازه استفاده دارد")
                return
            if not event.reply_to:
                await event.reply("❌ باید روی پیام موردنظر ریپلای کنید")
                return
            message_id = event.reply_to.reply_to_msg_id
            try:
                await bot.client.pin_message(chat_id, message_id, notify=False)
                save_pinned_message(chat_id, message_id)
                await event.reply("📌 پیام با موفقیت سنجاق شد.")
            except Exception as error:
                bot.logger.log_error(f"خطا در سنجاق پیام: {error}")
                await event.reply("❌ سنجاق پیام انجام نشد")
            return

        if clean_text == "پیام سنجاق":
            message_id = get_pinned_message(chat_id)
            if not message_id:
                await event.reply("📌 پیامی سنجاق نشده است.")
                return
            try:
                pinned = await bot.client.get_messages(chat_id, ids=message_id)
                content = getattr(pinned, "message", None) if pinned else None
                await event.reply(content or "📌 پیام سنجاق‌شده قابل نمایش نیست.")
            except Exception as error:
                bot.logger.log_error(f"خطا در نمایش پیام سنجاق: {error}")
                await event.reply("📌 پیام سنجاق‌شده قابل نمایش نیست.")
            return

        if clean_text in {"قفل", "باز"}:
            if not _has_group_management_permission(bot, chat_id, user_id, getattr(sender, 'username', None)):
                await event.reply("❌ فقط مالک یا ادمین ثبت‌شده اجازه استفاده دارد")
                return
            if clean_text == "قفل":
                bot.logger.log_info("LOCK COMMAND RECEIVED")
                await bot.group_actions.lock_group(chat_id)
                await event.reply("🔒 گروه قفل شد")
            else:
                bot.logger.log_info("UNLOCK COMMAND RECEIVED")
                await bot.group_actions.unlock_group(chat_id)
                await event.reply("🔓 گروه باز شد")
            return

        if clean_text == "راهنمای امتیاز":
            guide_text = (
                "🏅 راهنمای امتیاز\n\n"
                "🧩 حدس چیستان:\n+3 سکه\n\n"
                "😀 حدس ایموجی:\n+4 سکه\n\n"
                "🌍 حدس پرچم:\n+3 سکه\n\n"
                "📝 اسم فامیل (70 امتیاز یا بیشتر):\n+6 سکه\n\n"
                "✍️ تصحیح کلمات:\n+1 سکه\n\n"
                "❓ چهار گزینه‌ای:\n+3 سکه\n\n"
                "😂 بخند یا بباز:\n+1 سکه (اولین نفری که ایموجی خنده ارسال کند)\n\n"
                "🏕 بقا:\n+8 سکه (برنده نهایی)\n\n"
                "🧛 خون‌آشام:\n+7 سکه (حدس صحیح خون‌آشام)\n\n"
                "🧩 معما:\nپاسخ صحیح: ۳ سکه برنز\n\n"
                "🎯 بهترین جواب:\nبا ارسال بهترین و کاربردی‌ترین پاسخ به سوال، برنده انتخاب می‌شود.\n🪙 جایزه: ۲ سکه برنز\n\n"
                "⚔️ نبرد:\nبرنده: ۲ سکه برنز (اگر مساوی شود هر دو ۲ سکه برنز)\n\n"
                "📈 پایان هر روز:\n\n"
                "🥇 رتبه اول:\n+12 سکه\n\n"
                "🥈 رتبه دوم:\n+8 سکه\n\n"
                "🥉 رتبه سوم:\n+5 سکه"
            )
            def guide_u16(value):
                return len(value.encode("utf-16-le")) // 2
            guide_labels = ("🏅 راهنمای امتیاز", "🧩 حدس چیستان:", "😀 حدس ایموجی:", "🌍 حدس پرچم:", "📝 اسم فامیل (70 امتیاز یا بیشتر):", "✍️ تصحیح کلمات:", "❓ چهار گزینه‌ای:", "😂 بخند یا بباز:", "🏕 بقا:", "🧛 خون‌آشام:", "🧩 معما:", "🎯 بهترین جواب:", "⚔️ نبرد:", "📈 پایان هر روز:", "🥇 رتبه اول:", "🥈 رتبه دوم:", "🥉 رتبه سوم:")
            entities = [MessageEntityBold(offset=guide_u16(guide_text[:guide_text.index(label)]), length=guide_u16(label)) for label in guide_labels]
            await event.reply(guide_text, formatting_entities=entities)
            return

        if clean_text == "امتیاز من":
            profile = get_coin_profile(chat_id, user_id)
            activity = get_activity(chat_id, user_id)
            first = activity.get("first", 0)
            membership_days = 0
            if first:
                from time import time as _time
                membership_days = max(0, int((_time() - first) // 86400))
            profile_text = (
                "🏅 پروفایل امتیاز\n\n"
                f"ᯓ نام کاربری: {_format_admin_display(sender)}\n\n"
                f"🥉 برنز: ← {_math_digits(profile.get(economy.BRONZE, 0))}\n\n"
                f"🥈 نقره: ← {_math_digits(profile.get(economy.SILVER, 0))}\n\n"
                f"🥇 طلا: ← {_math_digits(profile.get(economy.GOLD, 0))}\n\n"
                f"💎 ارزش کل: ← {_math_digits(profile.get('total_coin_value', 0))}\n\n"
                f"🏆 رتبه: ← {_math_digits(coin_rank(chat_id, user_id)) if coin_rank(chat_id, user_id) else 'ندارد'}\n\n"
                f"🎮 برد در بازی‌ها: ← {_math_digits(profile.get('wins', 0))}\n\n"
                f"📅 مدت عضویت: 「 {_math_digits(membership_days)} 」"
            )
            def profile_u16(value):
                return len(value.encode("utf-16-le")) // 2
            labels = ("🏅 پروفایل امتیاز", "ᯓ نام کاربری:", "🥉 برنز:", "🥈 نقره:", "🥇 طلا:", "💎 ارزش کل:", "🏆 رتبه:", "🎮 برد در بازی‌ها:", "📅 مدت عضویت:")
            entities = []
            for label in labels:
                pos = profile_text.index(label)
                entities.append(MessageEntityBold(offset=profile_u16(profile_text[:pos]), length=profile_u16(label)))
            duration = f"「 {_math_digits(membership_days)} 」"
            duration_pos = profile_text.index(duration)
            entities.append(MessageEntityBlockquote(offset=profile_u16(profile_text[:duration_pos]), length=profile_u16(duration)))
            await event.reply(profile_text, formatting_entities=entities)
            return

        if clean_text == "رتبه ها":
            # رتبه‌بندی فقط بر پایهٔ ارزش کل؛ در تساوی، هرکس زودتر رسیده بالاتر.
            ranking = coin_leaderboard(chat_id, 5)
            # شمارهٔ رتبه با ایموجی عددی نمایش داده می‌شود؛ مدال‌های
            # 🥇🥈🥉 فقط برای «نوع سکه» در خط دوم می‌مانند.
            rank_digits = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
                           "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
            ranking_text = "🏆 برترین کاربران"
            entries = []
            for index, row in enumerate(ranking, 1):
                number = (rank_digits[index - 1] if index <= len(rank_digits)
                          else f"{_math_digits(index)}.")
                display = row.get("name") or f"کاربر {row['user_id']}"
                entry = (
                    f"{number} {display} — 💎 {_math_digits(row['total_coin_value'])}"
                    f"\n🥉 {_math_digits(row['bronze'])} | "
                    f"🥈 {_math_digits(row['silver'])} | "
                    f"🥇 {_math_digits(row['gold'])}"
                )
                entries.append(entry)
            if entries:
                ranking_text += "\n\n" + "\n\n".join(entries)
            else:
                ranking_text += "\n\nندارد"
            def ranking_u16(value):
                return len(value.encode("utf-16-le")) // 2
            entities = [MessageEntityBold(offset=0, length=ranking_u16("🏆 برترین کاربران"))]
            cursor = len("🏆 برترین کاربران\n\n")
            for entry in entries:
                entities.append(MessageEntityBlockquote(offset=ranking_u16(ranking_text[:cursor]), length=ranking_u16(entry)))
                cursor += len(entry) + 2
            await event.reply(ranking_text, formatting_entities=entities)
            return

        if clean_text == "آمارم":
            activity = get_activity(chat_id, user_id)
            group_stats = get_stats(chat_id)
            user_stats = group_stats.get('users', {}).get(str(user_id), {})
            messages = user_stats.get('messages', 0)
            violations = bot.tracker.get_count(chat_id, user_id)
            hours = max(0, (activity.get('last', 0) - activity.get('first', 0)) / 3600)
            score = min(10, max(1, (messages // 10) + activity.get('gifs', 0) + activity.get('videos', 0)))
            display_name = " ".join(part for part in (getattr(sender, 'first_name', None), getattr(sender, 'last_name', None)) if part) or str(user_id)
            stats_text = (
                f"📆 تاریخ : 『 {_jalali_today()} 』\n\n"
                f"                 ⟣ {display_name} ⟢\n\n"
                "     ═───────◇───────═\n\n"
                f"● تعداد پیام [ {_math_digits(messages)} ]\n\n"
                f"● تعداد گیف [ {_math_digits(activity.get('gifs', 0))} ]\n\n"
                f"● تعداد تخلف [ {_math_digits(violations)} ]\n\n"
                f"● تعداد فیلم‌ها [ {_math_digits(activity.get('videos', 0))} ]\n\n"
                f"● ساعاتی که داخل گروه فعالیت کرد [ {_math_digits(f'{hours:.1f}')} ]\n\n"
                f"⎋ [ امتیاز کاربر: {_math_digits(score)} از {_math_digits(10)} ]"
            )
            score_text = f"⎋ [ امتیاز کاربر: {_math_digits(score)} از {_math_digits(10)} ]"
            score_offset = len(stats_text[:stats_text.index(score_text)].encode("utf-16-le")) // 2
            await event.reply(
                stats_text,
                formatting_entities=[
                    MessageEntityBlockquote(
                        offset=score_offset,
                        length=len(score_text.encode("utf-16-le")) // 2,
                    )
                ],
            )
            return

        if clean_text == "ثبت مالک":
            _log_command_route(bot, clean_text, "ثبت مالک", "group_owner.set")
            if not is_global_owner(getattr(sender, "id", None)):
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
                    f"مالک گروه 『 {_format_group_member(target_user)} 』 ثبت شد ✅"
                )
            except Exception as e:
                bot.logger.log_error(f"خطا در ثبت مالک گروه: {e}")
                await event.reply(f"❌ خطا در ثبت مالک: {e}")
            return

        if clean_text == "لغو مالک":
            _log_command_route(bot, clean_text, "لغو مالک", "group_owner.remove")
            if not is_global_owner(getattr(sender, "id", None)):
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
            _log_command_route(bot, clean_text, "ثبت گروه", "group_registration")

            try:
                if not is_global_owner(getattr(sender, "id", None)):
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

                await event.reply(f"↻- گروه\n\n⏌ {title} ⎾ ثبت شد ☑️")

            except Exception as e:
                await event.reply(
                    f"❌ خطا در ثبت گروه: {e}"
                )

            return


        # فعال و غیرفعال کردن گروه توسط مالک اصلی
        # ثبت ادمین توسط مالک ربات

        _reserved_command, _reserved_handler = match_reserved_command(clean_text)

        if _reserved_command == "ثبت ادمین":
            _log_command_route(bot, clean_text, _reserved_command, _reserved_handler)
            if not _can_manage_group_admins(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply(
                    "❌ فقط مالک اصلی ربات یا مالک همین گروه اجازه مدیریت ادمین‌ها را دارد"
                )
                return

            try:
                admin_user = None
                if event.reply_to:
                    reply_msg = await bot.client.get_messages(
                        chat_id, ids=event.reply_to.reply_to_msg_id
                    )
                    if reply_msg:
                        admin_user = await reply_msg.get_sender()

                if not admin_user:
                    parts = clean_text.split()
                    if len(parts) >= 3:
                        admin_user = await bot.client.get_entity(parts[2])

                if not admin_user:
                    await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                    return

                admin_username = getattr(admin_user, "username", None)
                if add_admin(chat_id, admin_user.id, admin_username):
                    await event.reply(
                        f"✅ ادمین {_format_admin_display(admin_user)} ثبت شد"
                    )
                else:
                    await event.reply("⚠️ این کاربر قبلا ادمین ثبت شده است")

            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return


        # حذف ادمین توسط مالک اصلی یا مالک ثبت‌شده گروه
        if _reserved_command in {"برکناری ادمین", "لغو ادمین"}:
            _log_command_route(bot, clean_text, _reserved_command, _reserved_handler)
            if not _can_manage_group_admins(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply(
                    "❌ فقط مالک اصلی ربات یا مالک همین گروه اجازه مدیریت ادمین‌ها را دارد"
                )
                return

            try:
                admin_user = None
                if event.reply_to:
                    reply_msg = await bot.client.get_messages(
                        chat_id, ids=event.reply_to.reply_to_msg_id
                    )
                    if reply_msg:
                        admin_user = await reply_msg.get_sender()

                if not admin_user:
                    parts = clean_text.split()
                    if len(parts) >= 3:
                        admin_user = await bot.client.get_entity(parts[2])

                if not admin_user:
                    await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                    return

                admin_username = getattr(admin_user, "username", None)
                if remove_admin(chat_id, admin_user.id):
                    await event.reply(
                        f"✅ دسترسی ادمین {_format_admin_display(admin_user)} حذف شد"
                    )
                else:
                    await event.reply("❌ این کاربر ادمین ثبت‌شده نیست")

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

                # cooldown و Lock برای کل گروه، نه فقط هر کاربر؛ تا چند
                # ادمینِ هم‌زمان روی هم نیفتند و محدودیت ۵ ثانیه رعایت شود.
                if not _delete_cooldown_allowed(chat_id):
                    await event.reply(
                        "لطفا ۵ ثانیه صبر کنید تا پاکسازی قبلی کامل شود ⏳"
                    )
                    return
                lock = _delete_group_lock(chat_id)
                async with lock:
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

                # cooldown و Lock برای کل گروه (مشترک با «پاک عدد»).
                if not _delete_cooldown_allowed(chat_id):
                    await event.reply(
                        "لطفا ۵ ثانیه صبر کنید تا پاکسازی قبلی کامل شود ⏳"
                    )
                    return

                if not event.reply_to:
                    await event.reply("❌ باید روی پیام ریپلای کنید")
                    return

                lock = _delete_group_lock(chat_id)
                async with lock:
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

                async def kick_succeeded(_result):
                    add_kick(chat_id)
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
                        source="manual",
                    )
                    await event.reply("✅ کاربر اخراج شد")

                async def kick_failed(_error):
                    await event.reply("❌ اخراج کاربر انجام نشد")

                bot.moderation_queue.enqueue(
                    chat_id,
                    "kick",
                    user_id=target_user.id,
                    timeout_seconds=20,
                    operation=lambda: bot.client.edit_permissions(
                        chat_id, target_user, until_date=None, view_messages=False
                    ),
                    on_success=kick_succeeded,
                    on_failure=kick_failed,
                )

            except Exception as e:
                bot.logger.log_error(f"خطای اخراج: {e}")
                await event.reply(f"❌ خطا در اخراج:\n{e}")

            return


# آزاد کردن کاربر محروم شده
        if clean_text == "آزاد":
            if not _has_group_management_permission(
                bot, chat_id, user_id, getattr(sender, "username", None)
            ):
                await event.reply("❌ فقط مالک یا ادمین ثبت‌شده اجازه استفاده دارد")
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
                    f"⚠️ کاربر 「 {_format_banned_user(user, user.id)} 」\n\n"
                    "اخطار دریافت کرد "
                    f"تعداد اخطار: {_math_digits(count)}/{_math_digits(threshold)}"
                )

                if bot.tracker.should_punish(chat_id, user.id):
                    async def warning_punish_succeeded(_result):
                        if (
                            count >= 5
                            and bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                        ):
                            await _send_moderation_notification_once(
                                bot, chat_id, user.id, "warning_ban", event.message.id,
                                "🚫 کاربر 「"
                                f"{_format_banned_user(user, user.id)}"
                                "」\nبه دلیل تخلفات از گروه اخراج شد.",
                            )

                    bot.moderation_queue.enqueue(
                        chat_id,
                        "punish",
                        user_id=user.id,
                        timeout_seconds=20,
                        operation=lambda: bot.admin_actions.punish_user(
                            chat_id, user.id, username, announce=False
                        ),
                        on_success=warning_punish_succeeded,
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

                async def mute_succeeded(_result):
                    add_mute(chat_id)
                    await event.reply(
                        f"🔕 کاربر 『 {_format_banned_user(target_user, target_user.id)} 』 سکوت شد"
                    )

                async def mute_failed(_error):
                    await event.reply("❌ انجام سکوت ناموفق بود")

                bot.moderation_queue.enqueue(
                    chat_id,
                    "mute",
                    user_id=target_user.id,
                    timeout_seconds=15,
                    operation=lambda: bot.admin_actions.mute_user(chat_id, target_user.id),
                    on_success=mute_succeeded,
                    on_failure=mute_failed,
                )

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

                async def unmute_succeeded(_result):
                    add_mute(chat_id)
                    await event.reply("🔊 سکوت کاربر برداشته شد")

                async def unmute_failed(_error):
                    await event.reply("❌ رفع سکوت انجام نشد")

                bot.moderation_queue.enqueue(
                    chat_id,
                    "unmute",
                    user_id=target_user.id,
                    timeout_seconds=15,
                    operation=lambda: bot.admin_actions.unmute_user(chat_id, target_user.id),
                    on_success=unmute_succeeded,
                    on_failure=unmute_failed,
                )

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


        profiler.mark("FILTER")
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

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key = f"{chat_id}:{user_id}"
                _log_ban_execution(bot, chat_id, user_id, "تکرار شدید داخل پیام")

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    async def heavy_repeat_succeeded(_result):
                        if bot.config_manager.get("action_on_threshold") in ["ban", "kick"]:
                            await _send_moderation_notification_once(
                                bot, chat_id, user_id, "spam_ban", event.message.id,
                                "⚠️ کاربر ⏌ "
                                f"{_format_banned_user(sender, user_id)}"
                                " ⎾\n\nبه دلیل هرزنامه از گروه اخراج شد.",
                            )
                        await _cleanup_heavy_spam_history(bot, event, chat_id, user_id)

                    async def heavy_repeat_failed(_error):
                        bot.punished_users.discard(punish_key)

                    bot.moderation_queue.enqueue(
                        chat_id,
                        "punish",
                        user_id=user_id,
                        timeout_seconds=20,
                        operation=lambda: bot.admin_actions.punish_user(
                            chat_id, user_id, username, announce=False
                        ),
                        on_success=heavy_repeat_succeeded,
                        on_failure=heavy_repeat_failed,
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

        # مدیر/مالک ثبت‌شده از فیلتر خودکار و فیلتر کلمات گروه عبور می‌کند،
        # اما اجرای راهنما، بازی‌ها و فرمان‌های مدیریت باید ادامه داشته باشد.
        if is_group_moderator:
            print(f"✅ ADMIN BYPASS FILTER: {sender_username}")
            is_spam = False
            reason = ""
        elif group_word_spam:
            is_spam = True
            reason = group_word_reason
        else:
            is_spam, reason = bot.detector.is_spam(message_text, chat_id)

        profiler.mark("SPAM_CHECK")
        if is_spam:
            profiler.mark("AUTO_MODERATION")
            rejoin_state = getattr(bot, "rejoin_spam_state", {}).get(
                (chat_id, user_id), {}
            )
            if rejoin_state.get("previously_banned"):
                bot.logger.log_info(
                    "SPLUS REJOIN STATE DEBUG\n"
                    f"user_id={user_id}\n"
                    f"chat_id={chat_id}\n"
                    "previously_banned=True\n"
                    f"previous_violations={rejoin_state.get('previous_violations', 0)}\n"
                    "new_spam_detected=True\n"
                    f"ban_triggered={f'{chat_id}:{user_id}' not in bot.punished_users}"
                )

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
                        _log_ban_execution(bot, chat_id, user_id, "اسپم تکراری شدید")
                        if punish_key not in bot.punished_users:
                            bot.punished_users.add(punish_key)
                            async def repeat_ban_succeeded(_result):
                                await _send_moderation_notification_once(
                                    bot, chat_id, user_id, "spam_ban", event.message.id,
                                    "⚠️ کاربر ⏌ "
                                    f"{_format_banned_user(sender, user_id)}"
                                    " ⎾\n\nبه دلیل هرزنامه از گروه اخراج شد.",
                                )

                            async def repeat_ban_failed(_error):
                                bot.punished_users.discard(punish_key)

                            bot.moderation_queue.enqueue(
                                chat_id,
                                "ban",
                                user_id=user_id,
                                timeout_seconds=20,
                                operation=lambda: bot.admin_actions.ban_user(
                                    chat_id, user_id, reason="اسپم مکرر شدید"
                                ),
                                on_success=repeat_ban_succeeded,
                                on_failure=repeat_ban_failed,
                            )

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
                _log_ban_execution(bot, chat_id, user_id, "رسیدن به آستانه تخلفات")

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    print(
                        f"⚠️ کاربر {username}({user_id}) به آستانه {threshold} رسید - اعمال مجازات"
                    )

                    async def threshold_punish_succeeded(_result):
                        permanent = bot.config_manager.get("action_on_threshold") in ["ban", "kick"]
                        if count >= 5 and permanent:
                            await _send_moderation_notification_once(
                                bot, chat_id, user_id, "warning_ban", event.message.id,
                                "🚫 کاربر 「"
                                f"{_format_banned_user(sender, user_id)}"
                                "」\nبه دلیل تخلفات از گروه اخراج شد.",
                            )
                        bot.tracker.reset_count(chat_id, user_id)
                        if not permanent:
                            bot.punished_users.discard(punish_key)

                    async def threshold_punish_failed(_error):
                        bot.punished_users.discard(punish_key)

                    bot.moderation_queue.enqueue(
                        chat_id,
                        "punish",
                        user_id=user_id,
                        timeout_seconds=20,
                        operation=lambda: bot.admin_actions.punish_user(
                            chat_id, user_id, username, announce=False
                        ),
                        on_success=threshold_punish_succeeded,
                        on_failure=threshold_punish_failed,
                    )
            # پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد
            pass

    except Exception as e:
        bot.logger.log_error(f"خطا در هندل پیام: {e}")
        import traceback
        traceback.print_exc()
    finally:
        profiler.set("SEND_RESPONSE", response_rpc_ms())
        profiler.finish(bot.logger, chat_id)
        end_response_measurement(response_token)

