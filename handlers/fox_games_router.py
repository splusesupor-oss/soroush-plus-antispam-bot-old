"""Command Router بازی‌های Fox AI.

تنها نقطهٔ اتصال این چهار بازی به ربات. هیچ state ای اینجا نگه داشته
نمی‌شود؛ همه چیز داخل ماژول خودِ بازی است.

``handle`` مقدار True برمی‌گرداند یعنی پیام مصرف شد و هندلر اصلی نباید
ادامه دهد.
"""
from modules.coins import award as coins_award
from modules.fox_games import laugh_or_lose, lucky_box, survival, vampire
from modules.fox_games.session_core import (
    log,
    log_error,
    normalize_text,
    to_persian_digits,
)

# دستورهایی که این روتر مالک آن‌هاست.
FOX_GAME_COMMANDS = frozenset({
    "بخند یا بباز",
    "بقا",
    "جعبه شانسی",
    "خون آشام",
    "خون‌آشام",
})


def any_active(chat_id):
    """آیا یکی از بازی‌های Fox در این چت فعال است."""
    return (
        laugh_or_lose.is_active(chat_id)
        or survival.is_active(chat_id)
        or lucky_box.is_active(chat_id)
        or vampire.is_active(chat_id)
    )


def _coins(bot, chat_id, user_id, name, amount, logger=None):
    """سکه را مستقیماً به موجودی کاربر اضافه می‌کند.

    از خودِ ماژول coins استفاده می‌شود، نه یک attribute روی bot: شیء ربات
    متد ``award_coins`` ندارد و اتکا به آن باعث می‌شد هیچ جایزه‌ای پرداخت
    نشود. اگر تست یا کد دیگری متد را روی bot گذاشته باشد، همان ترجیح دارد.
    """
    award = getattr(bot, "award_coins", None) or coins_award
    try:
        balance = award(chat_id, user_id, name, amount)
        log(logger, f"FOX REWARD PAID chat_id={chat_id} user_id={user_id} "
                    f"amount={amount} balance={balance}")
        return True
    except Exception as error:
        log_error(logger, f"FOX REWARD FAILED chat_id={chat_id} "
                          f"user_id={user_id} amount={amount} error={error!r}")
        return False


# ---------------------------------------------------------------------------
# 😂 بخند یا بباز
# ---------------------------------------------------------------------------
async def _start_laugh(bot, event, chat_id, logger):
    if laugh_or_lose.is_active(chat_id):
        await event.reply(laugh_or_lose.ALREADY_RUNNING)
        return True
    session = laugh_or_lose.start(chat_id, logger)
    if session is None:
        await event.reply(laugh_or_lose.ALREADY_RUNNING)
        return True

    await event.reply("😂 بخند یا بباز\n\nآماده باش...")

    async def on_countdown(remaining):
        await event.reply(f"{to_persian_digits(remaining)}...")

    async def on_open():
        await event.reply(
            "😂 حالا بخند!\n\n"
            "اولین نفری که یکی از این ایموجی‌ها را بفرستد برنده است:\n"
            "😂 🤣 😆 😹 😄 😁"
        )

    async def on_timeout():
        await event.reply(laugh_or_lose.NO_WINNER)

    laugh_or_lose.schedule(
        chat_id, session["session_id"],
        on_countdown, on_open, on_timeout, logger=logger,
    )
    return True


async def _laugh_message(bot, event, chat_id, user_id, sender, text, logger):
    if not laugh_or_lose.is_accepting(chat_id):
        return False
    if not laugh_or_lose.contains_laugh(text):
        return False
    win = laugh_or_lose.claim_win(chat_id, user_id, sender, logger)
    if win is None:
        return False
    paid = _coins(bot, chat_id, user_id, win["name"], win["coins"], logger)
    reward = f"\n\n🪙 +{to_persian_digits(win['coins'])} سکه" if paid else ""
    await event.reply(f"🏆 برنده: {win['name']}{reward}")
    return True


# ---------------------------------------------------------------------------
# 🏕 بقا
# ---------------------------------------------------------------------------
async def _start_survival(bot, event, chat_id, logger):
    if survival.is_active(chat_id):
        await event.reply(survival.ALREADY_RUNNING)
        return True
    session = survival.start(chat_id, logger)
    if session is None:
        await event.reply(survival.ALREADY_RUNNING)
        return True

    await event.reply(
        "🏕 بازی بقا\n\n"
        f"برای شرکت بنویسید: {survival.JOIN_WORD}\n\n"
        f"ظرفیت: {to_persian_digits(survival.MAX_PLAYERS)} نفر\n"
        f"⏳ مهلت ثبت‌نام: {to_persian_digits(survival.JOIN_SECONDS)} ثانیه"
    )

    async def on_abort():
        await event.reply(survival.NOT_ENOUGH)

    async def on_begin(names):
        lines = "\n".join(
            f"{to_persian_digits(i)}. {n}" for i, n in enumerate(names, 1)
        )
        await event.reply(f"🏕 بازی شروع شد!\n\n{lines}")

    async def on_question(question):
        await event.reply(
            f"🏕 مرحله {to_persian_digits(question['level'])}\n\n"
            f"{question['text']}\n\n"
            f"⏳ {to_persian_digits(survival.ANSWER_SECONDS)} ثانیه"
        )

    async def on_eliminated(names):
        await event.reply("❌ حذف شدند:\n" + "\n".join(f"• {n}" for n in names))

    async def on_finish(champion):
        if champion is None:
            await event.reply("🏕 بازی بدون برنده تمام شد.")
            return
        paid = _coins(bot, chat_id, champion["user_id"], champion["name"],
                      survival.WINNER_COINS, logger)
        rounds = champion.get("round_coins", 0)
        lines = [f"🏆 برندهٔ بقا: {champion['name']}"]
        if paid:
            lines.append("")
            if rounds:
                lines.append(
                    f"🪙 سکهٔ مراحل: +{to_persian_digits(rounds)}"
                )
            lines.append(
                f"🪙 جایزهٔ برنده: +{to_persian_digits(survival.WINNER_COINS)}"
            )
            lines.append(
                f"مجموع این بازی: "
                f"{to_persian_digits(rounds + survival.WINNER_COINS)} سکه"
            )
        await event.reply("\n".join(lines))

    survival.schedule(chat_id, session["session_id"], {
        "on_abort": on_abort,
        "on_begin": on_begin,
        "on_question": on_question,
        "on_eliminated": on_eliminated,
        "on_finish": on_finish,
    }, logger=logger)
    return True


async def _survival_message(bot, event, chat_id, user_id, sender, text, logger):
    if not survival.is_active(chat_id):
        return False
    state = survival.phase(chat_id)
    normalized = normalize_text(text)

    if state == "joining":
        if normalized != normalize_text(survival.JOIN_WORD):
            return False
        result, players = survival.join(chat_id, user_id, sender, logger)
        if result == "joined":
            await event.reply(
                f"✅ ثبت شد ({to_persian_digits(len(players))}"
                f"/{to_persian_digits(survival.MAX_PLAYERS)})"
            )
        elif result == "duplicate":
            await event.reply("⚠️ شما قبلاً ثبت‌نام کرده‌اید.")
        elif result == "full":
            await event.reply("⚠️ ظرفیت تکمیل است.")
        return True

    if state == "playing":
        result, player = survival.answer(chat_id, user_id, text, logger)
        if result in {"no_question", "not_player"}:
            return False
        if result == "already":
            return True
        if result == "correct":
            # سکهٔ مرحله بلافاصله پرداخت می‌شود؛ حذف شدن در مراحل بعد آن را
            # پس نمی‌گیرد.
            paid = _coins(bot, chat_id, user_id, player["name"],
                          survival.CORRECT_COINS, logger)
            reward = (f" 🪙 +{to_persian_digits(survival.CORRECT_COINS)} سکه"
                      if paid else "")
            await event.reply(f"✅ درست بود!{reward}")
        elif result == "wrong":
            await event.reply("❌ پاسخ اشتباه — حذف شدید.")
        return True
    return False


# ---------------------------------------------------------------------------
# 🎁 جعبه شانسی
# ---------------------------------------------------------------------------
async def _start_lucky_box(bot, event, chat_id, user_id, logger):
    session, error = lucky_box.start(chat_id, user_id, logger)
    if error == "active":
        await event.reply(lucky_box.ALREADY_RUNNING)
        return True
    if error == "quota":
        await event.reply(lucky_box.quota_message(user_id))
        return True

    await event.reply(
        "🎁 جعبه شانسی\n\n"
        f"{lucky_box.BOARD}\n\n"
        "شماره یک جعبه را بفرستید (۱ تا ۹)"
    )

    async def on_timeout():
        await event.reply("⏰ زمان انتخاب جعبه تمام شد.")

    lucky_box.schedule(chat_id, session["session_id"], on_timeout, logger=logger)
    return True


async def _lucky_box_message(bot, event, chat_id, user_id, sender, text, logger):
    if not lucky_box.is_active(chat_id):
        return False
    result, error = lucky_box.pick(chat_id, user_id, text, logger)
    if error in {"not_owner", None} and result is None:
        return False
    if error == "bad_number":
        return False
    if error == "done":
        return True
    if result is None:
        return False

    if result["prize"] > 0:
        paid = _coins(bot, chat_id, user_id, "", result["prize"], logger)
        reward = f"\n🪙 +{to_persian_digits(result['prize'])} سکه" if paid else ""
        await event.reply(
            f"🎁 جعبه {to_persian_digits(result['box'])} باز شد!\n\n"
            f"🎉 جایزه: {to_persian_digits(result['prize'])} سکه{reward}"
        )
    else:
        await event.reply(
            f"🎁 جعبه {to_persian_digits(result['box'])} باز شد!\n\n😔 پوچ بود."
        )
    return True


# ---------------------------------------------------------------------------
# 🧛 خون‌آشام
# ---------------------------------------------------------------------------
async def _start_vampire(bot, event, chat_id, logger):
    if vampire.is_active(chat_id):
        await event.reply(vampire.ALREADY_RUNNING)
        return True
    session = vampire.start(chat_id, logger)
    if session is None:
        await event.reply(vampire.ALREADY_RUNNING)
        return True

    await event.reply(
        "🧛 بازی خون‌آشام\n\n"
        f"برای شرکت بنویسید: {vampire.JOIN_WORD}\n\n"
        f"حداقل {to_persian_digits(vampire.MIN_PLAYERS)} و حداکثر "
        f"{to_persian_digits(vampire.MAX_PLAYERS)} نفر\n"
        f"⏳ مهلت ثبت‌نام: {to_persian_digits(vampire.JOIN_SECONDS)} ثانیه"
    )

    async def on_abort():
        await event.reply(vampire.NOT_ENOUGH)

    async def on_roles(chosen):
        await event.reply(
            "🧛 شرکت‌کنندگان:\n\n"
            f"{vampire.roster_lines(chosen['players'])}\n\n"
            f"{vampire.CHOSEN_MESSAGE}\n\n"
            "شمارهٔ خون‌آشام را حدس بزنید (هر نفر فقط یک بار)"
        )
        # نقش فقط در پیوی خودِ خون‌آشام اعلام می‌شود.
        try:
            await bot.client.send_message(
                chosen["player"]["user_id"], vampire.ROLE_MESSAGE
            )
            log(logger, f"FOX VAMPIRE ROLE SENT chat_id={chat_id} "
                        f"user_id={chosen['player']['user_id']}")
        except Exception as error:
            log_error(logger, f"FOX VAMPIRE ROLE DM FAILED chat_id={chat_id} "
                              f"user_id={chosen['player']['user_id']} error={error!r}")

    async def on_timeout(revealed):
        await event.reply(vampire.format_reveal(revealed))

    vampire.schedule(chat_id, session["session_id"], {
        "on_abort": on_abort,
        "on_roles": on_roles,
        "on_timeout": on_timeout,
    }, logger=logger)
    return True


async def _vampire_message(bot, event, chat_id, user_id, sender, text, logger):
    if not vampire.is_active(chat_id):
        return False
    state = vampire.phase(chat_id)
    normalized = normalize_text(text)

    if state == "joining":
        if normalized != normalize_text(vampire.JOIN_WORD):
            return False
        result, players = vampire.join(chat_id, user_id, sender, logger)
        if result == "joined":
            await event.reply(
                f"✅ ثبت شد ({to_persian_digits(len(players))}"
                f"/{to_persian_digits(vampire.MAX_PLAYERS)})"
            )
        elif result == "duplicate":
            await event.reply("⚠️ شما قبلاً ثبت‌نام کرده‌اید.")
        elif result == "full":
            await event.reply("⚠️ ظرفیت تکمیل است.")
        return True

    if state == "guessing":
        result, info = vampire.guess(chat_id, user_id, text, logger)
        if result in {"closed", "not_player", "bad_number"}:
            return False
        if result == "self_guess":
            await event.reply("⚠️ نمی‌توانید خودتان را انتخاب کنید.")
            return True
        if result in {"already", "is_vampire"}:
            return True
        if result == "wrong":
            await event.reply(f"❌ اشتباه بود، {info['guesser']['name']}!")
            return True
        if result == "correct":
            paid = _coins(bot, chat_id, user_id, info["guesser"]["name"],
                          info["coins"], logger)
            reward = (f"\n🪙 +{to_persian_digits(info['coins'])} سکه"
                      if paid else "")
            v_name = info["vampire"]["name"]
            v_tag = info["vampire"].get("tag") or ""
            tag = f" ({v_tag})" if v_tag and v_tag != v_name else ""
            await event.reply(
                f"🎯 درست حدس زدی، {info['guesser']['name']}!{reward}\n\n"
                f"🧛 خون‌آشام: {v_name}{tag}"
            )
            return True
    return False


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
async def handle(bot, event, chat_id, user_id, sender, text, logger=None):
    """پیام را به بازی مربوطه می‌سپارد. True یعنی پیام مصرف شد."""
    command = normalize_text(text)

    if command == normalize_text("بخند یا بباز"):
        return await _start_laugh(bot, event, chat_id, logger)
    if command == normalize_text("بقا"):
        return await _start_survival(bot, event, chat_id, logger)
    if command == normalize_text("جعبه شانسی"):
        return await _start_lucky_box(bot, event, chat_id, user_id, logger)
    if command in {normalize_text("خون آشام"), normalize_text("خون‌آشام")}:
        return await _start_vampire(bot, event, chat_id, logger)

    # پیام‌های درون‌بازی — هر بازی فقط session خودش را می‌بیند.
    for responder in (
        _laugh_message, _survival_message, _lucky_box_message, _vampire_message,
    ):
        if await responder(bot, event, chat_id, user_id, sender, text, logger):
            return True
    return False


def reset_all(chat_id=None):
    laugh_or_lose.reset_all(chat_id)
    survival.reset_all(chat_id)
    lucky_box.reset_all(chat_id)
    vampire.reset_all(chat_id)
