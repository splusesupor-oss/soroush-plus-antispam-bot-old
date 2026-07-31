"""👤 تست بازطراحی کامل پروفایل.

پوشش:
    • ثبت اطلاعات اولیه (اسم ← شهر ← سن ← لقب اختیاری)
    • ماندگاری اطلاعات و نمایش مستقیم از دفعهٔ دوم
    • ظاهر دقیق کارت پروفایل مطابق نمونهٔ خواسته‌شده
    • قوانین عنوان پویا (لقب / یوزرنیم / اسم + اولین نشان)
    • بخش «📦 لیست آیتم‌ها» و Bold بودن کل آن
    • اتصال کامل خرید به اقتصاد فعلی (کسر واقعی سکه)
    • نمایش فوری نشان/لقب/ستاره پس از خرید
    • عبور از *همان* هندلر واقعی ربات

    python tests/test_profile.py
"""
import asyncio
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import economy
import economy.shop.store as store
import economy.storage as storage
import handlers.economy_handler as eco_handler
from economy import catalog, profiles
from economy.ui import balance_menu, profile_menu, shop_menu

PASSED = FAILED = 0
CHAT = -1009999888877
OTHER_CHAT = -100555444333


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# ---------------------------------------------------------------------------
# دوبل‌های سبک
# ---------------------------------------------------------------------------
class Logger:
    def __init__(self):
        self.info, self.errors = [], []

    def log_info(self, message):
        self.info.append(message)

    def log_error(self, message):
        self.errors.append(message)

    def has(self, needle):
        return any(needle in m for m in self.info + self.errors)


class Bot:
    def __init__(self):
        self.logger = Logger()


class User:
    def __init__(self, uid, name="علی", last=None, username=None):
        self.id = uid
        self.first_name = name
        self.last_name = last
        self.username = username


class Message:
    _next = 5000

    def __init__(self):
        Message._next += 1
        self.id = Message._next


class Event:
    def __init__(self):
        self.replies = []
        self.entity_counts = []
        self.message = Message()
        self.reply_to = None

    async def reply(self, text, **kwargs):
        self.replies.append(text)
        self.entity_counts.append(len(kwargs.get("formatting_entities") or []))
        return None

    def said(self, needle):
        return any(needle in m for m in self.replies)

    @property
    def last(self):
        return self.replies[-1] if self.replies else ""


def fresh():
    temp = Path(tempfile.mkdtemp())
    storage.use_file(temp / "economy.json")
    store.ITEMS_FILE = temp / "shop.json"
    store._cache = None
    store._cache_mtime = None
    eco_handler.reset_all()
    return temp


async def send(bot, event, user_id, text, sender=None):
    return await eco_handler.handle(
        bot, event, CHAT, user_id, sender or User(user_id), text, bot.logger)


def fund(user_id, bronze=0, silver=0, gold=0, chat=CHAT):
    if bronze:
        economy.add_bronze(chat, user_id, bronze)
    if silver:
        economy.add_silver(chat, user_id, silver)
    if gold:
        economy.add_gold(chat, user_id, gold)


# ===========================================================================
# ۱) ثبت اطلاعات اولیه
# ===========================================================================
def test_registration_flow():
    print("\n### 👤 ثبت اطلاعات اولیه")
    fresh()

    async def scenario():
        bot = Bot()
        steps = []
        for text in ("پروفایل", "علی", "شیراز", "20", "Fox King"):
            event = Event()
            await send(bot, event, 1, text)
            steps.append(event)
        return bot, steps

    bot, steps = asyncio.run(scenario())
    check("اول اسم پرسیده می‌شود", steps[0].said("اسم"))
    check("سپس شهر پرسیده می‌شود", steps[1].said("شهر"))
    check("سپس سن پرسیده می‌شود", steps[2].said("سن"))
    check("سپس لقب پرسیده می‌شود", steps[3].said("لقب"))
    check("لقب اختیاری بودنش اعلام می‌شود", steps[3].said("اختیاری"))
    check("در پایان تأیید ثبت می‌آید", steps[4].said("ثبت شد"))
    check("کارت بلافاصله نمایش داده می‌شود", steps[4].said("👤 نام: علی"))

    saved = profiles.get(CHAT, 1)
    check("اسم ذخیره شد", saved["name"] == "علی")
    check("شهر ذخیره شد", saved["city"] == "شیراز")
    check("سن ذخیره شد", saved["age"] == 20)
    check("لقب ذخیره شد", saved["nickname"] == "Fox King")
    check("پرچم ثبت‌شده روشن شد", saved["registered"] is True)
    check("ورود ثبت‌نام لاگ شد", bot.logger.has("PROFILE REGISTRATION START"))
    check("پایان ثبت‌نام لاگ شد", bot.logger.has("PROFILE REGISTERED"))
    eco_handler.reset_all()


def test_registration_optional_nickname():
    print("\n### 👤 لقب واقعاً اختیاری است")
    fresh()

    async def scenario():
        bot = Bot()
        for text in ("پروفایل", "رضا", "تهران", "۳۱", "۰"):
            await send(bot, Event(), 2, text)
        return bot

    asyncio.run(scenario())
    saved = profiles.get(CHAT, 2)
    check("ثبت با رد کردن لقب کامل شد", saved["registered"] is True)
    check("لقب خالی ماند", saved["nickname"] is None)
    check("سن با ارقام فارسی پذیرفته شد", saved["age"] == 31)
    eco_handler.reset_all()


def test_registration_validation():
    print("\n### 👤 اعتبارسنجی ورودی ثبت‌نام")
    fresh()

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 3, "پروفایل")
        await send(bot, Event(), 3, "سارا")
        await send(bot, Event(), 3, "اصفهان")
        bad = Event()
        await send(bot, bad, 3, "بیست")
        good = Event()
        await send(bot, good, 3, "20")
        return bad, good

    bad, good = asyncio.run(scenario())
    check("سن غیرعددی رد می‌شود", bad.said("عدد"))
    check("پس از خطا دوباره همان مرحله ادامه دارد", good.said("لقب"))

    long_name = "ا" * (profiles.MAX_NAME + 5)
    try:
        profiles.validate_name(long_name)
        check("اسم بیش‌ازحد بلند رد می‌شود", False)
    except profiles.ProfileError:
        check("اسم بیش‌ازحد بلند رد می‌شود", True)
    try:
        profiles.validate_age("500")
        check("سن خارج از بازه رد می‌شود", False)
    except profiles.ProfileError:
        check("سن خارج از بازه رد می‌شود", True)
    eco_handler.reset_all()


def test_second_time_shows_card_directly():
    print("\n### 👤 دفعهٔ دوم مستقیم کارت")
    fresh()
    profiles.register(CHAT, 4, name="مینا", city="رشت", age=24)

    async def scenario():
        bot = Bot()
        event = Event()
        await send(bot, event, 4, "پروفایل")
        return event

    event = asyncio.run(scenario())
    check("هیچ سؤالی پرسیده نمی‌شود", not event.said("اسم خود را"))
    check("مستقیم کارت می‌آید", event.said("👤 نام: مینا"))
    check("شهر ذخیره‌شده دیده می‌شود", event.said("📍 شهر: رشت"))
    check("سن ذخیره‌شده دیده می‌شود", event.said("🎂 سن: ۲۴ سال"))
    eco_handler.reset_all()


def test_profile_is_per_group():
    print("\n### 👤 پروفایل per-group است")
    fresh()
    profiles.register(CHAT, 5, name="حسین", city="یزد", age=30)
    other = profiles.get(OTHER_CHAT, 5)
    check("پروفایل به گروه دیگر نشت نمی‌کند", other["registered"] is False)
    check("پروفایل گروه خودش سرجایش است",
          profiles.get(CHAT, 5)["name"] == "حسین")


# ===========================================================================
# ۲) ظاهر پروفایل
# ===========================================================================
def test_card_layout_matches_sample():
    print("\n### 🎨 ظاهر کارت دقیقاً مطابق نمونه")
    fresh()
    fund(6, bronze=6000, silver=6000)
    profiles.register(CHAT, 6, name="علی", city="شیراز", age=20)
    for item in ("badge_fox", "badge_king", "badge_bolt", "star_3",
                 "title_fox_king"):
        profiles.buy(CHAT, 6, item)

    import economy.coins.accounts as accounts
    with storage.transaction() as data:
        user = accounts._user(data, accounts.user_key(CHAT, 6))
        user["bronze"], user["silver"], user["gold"] = 1420, 18, 3
        accounts._refresh_total(data, user)

    text, spans = profile_menu.render_card(CHAT, 6, User(6, "علی"))
    expected = (
        "╔════════════════════╗\n"
        "🦊 𝙁𝙤𝙭 𝙆𝙞𝙣𝙜 🦊\n"
        "╚════════════════════╝\n"
        "\n"
        "👤 نام: علی\n"
        "🏷 لقب: 𝙁𝙤𝙭 𝙆𝙞𝙣𝙜\n"
        "\n"
        "🛡 نشان‌ها:\n"
        "🦊 👑 ⚡\n"
        "\n"
        "⭐ سطح: ★★★☆☆☆☆\n"
        "\n"
        "🥉 برنز: ۱۴۲۰\n"
        "🥈 نقره: ۱۸\n"
        "🥇 طلا: ۳\n"
        "\n"
        "📍 شهر: شیراز\n"
        "🎂 سن: ۲۰ سال\n"
        "\n"
        "🎮 برد: ۰\n"
        "🏅 رتبه: #۱"
    )
    check("خروجی کاراکتربه‌کاراکتر با نمونه یکی است", text == expected,
          f"\n--- گرفته شد ---\n{text}\n--- انتظار ---\n{expected}")
    check("کادر بالا هست", text.startswith(profile_menu.BOX_TOP))
    check("کادر پایین هست", profile_menu.BOX_BOTTOM in text)
    check("عنوان Bold است", any(kind == "bold" for kind, _, _ in spans))


def test_card_keeps_all_fields():
    print("\n### 🎨 هیچ فیلدی حذف نشده")
    fresh()
    fund(7, bronze=500, silver=40, gold=2)
    profiles.register(CHAT, 7, name="نیما", city="کرج", age=19)
    text, _ = profile_menu.render_card(CHAT, 7, User(7, "نیما"))
    for field in ("🥉 برنز:", "🥈 نقره:", "🥇 طلا:", "🎮 برد:", "🏅 رتبه:",
                  "📍 شهر:", "🎂 سن:", "🛡 نشان‌ها:", "⭐ سطح:", "👤 نام:"):
        check(f"فیلد {field} حاضر است", field in text)
    check("برنز واقعی از اقتصاد خوانده می‌شود", "۵۰۰" in text)
    check("نقره واقعی از اقتصاد خوانده می‌شود", "۴۰" in text)
    check("طلا واقعی از اقتصاد خوانده می‌شود", "🥇 طلا: ۲" in text)


def test_numbers_have_no_thousand_separator():
    print("\n### 🎨 اعداد بدون جداکنندهٔ هزارگان")
    fresh()
    fund(8, bronze=1420)
    profiles.register(CHAT, 8, name="سعید", city="اهواز", age=22)
    text, _ = profile_menu.render_card(CHAT, 8, User(8, "سعید"))
    check("۱۴۲۰ بدون کاما نوشته می‌شود", "۱۴۲۰" in text)
    check("هیچ جداکننده‌ای نیست", "٬" not in text and "," not in text)


# ===========================================================================
# قوانین عنوان پویا
# ===========================================================================
def test_title_rules():
    print("\n### 🏷 قوانین عنوان بالای کارت")
    fresh()
    fund(10, silver=3000)
    fund(11, silver=3000)
    fund(12, silver=3000)

    # ۱) لقب + اولین نشان
    profiles.register(CHAT, 10, name="علی", city="شیراز", age=20,
                      nickname="Fox King")
    profiles.buy(CHAT, 10, "badge_fox")
    profiles.buy(CHAT, 10, "badge_king")
    title = profile_menu.build_title(profiles.get(CHAT, 10),
                                     User(10, "علی", username="aliii"))
    check("لقب مقدم بر یوزرنیم است", title == "🦊 Fox King 🦊", f"-> {title!r}")

    # ۲) بدون لقب ولی با یوزرنیم
    profiles.register(CHAT, 11, name="رضا", city="تهران", age=25)
    profiles.buy(CHAT, 11, "badge_wolf")
    title = profile_menu.build_title(profiles.get(CHAT, 11),
                                     User(11, "رضا", username="rezaa"))
    check("بدون لقب، یوزرنیم می‌آید", title == "🐺 @rezaa 🐺", f"-> {title!r}")

    # ۳) نه لقب نه یوزرنیم → اسم نمایشی
    profiles.register(CHAT, 12, name="مریم", city="قم", age=28)
    profiles.buy(CHAT, 12, "badge_lion")
    title = profile_menu.build_title(profiles.get(CHAT, 12),
                                     User(12, "مریم", last="احمدی"))
    check("بدون لقب و یوزرنیم، اسم نمایشی می‌آید",
          title == "🦁 مریم احمدی 🦁", f"-> {title!r}")


def test_title_without_any_badge():
    print("\n### 🏷 بدون نشان، هیچ ایموجی کنار عنوان نیست")
    fresh()
    profiles.register(CHAT, 13, name="سمیرا", city="تبریز", age=27,
                      nickname="Royal")
    title = profile_menu.build_title(profiles.get(CHAT, 13),
                                     User(13, "سمیرا", username="sami"))
    check("فقط لقب، بدون ایموجی", title == "Royal", f"-> {title!r}")

    profiles.register(CHAT, 14, name="بهرام", city="مشهد", age=33)
    title = profile_menu.build_title(profiles.get(CHAT, 14),
                                     User(14, "بهرام", username="bahram"))
    check("فقط یوزرنیم، بدون ایموجی", title == "@bahram", f"-> {title!r}")

    profiles.register(CHAT, 15, name="کامران", city="شیراز", age=40)
    title = profile_menu.build_title(profiles.get(CHAT, 15),
                                     User(15, "کامران"))
    check("فقط اسم، بدون ایموجی", title == "کامران", f"-> {title!r}")


def test_title_uses_first_bought_badge():
    print("\n### 🏷 عنوان از *اولین* نشان خریداری‌شده استفاده می‌کند")
    fresh()
    fund(16, silver=5000)
    profiles.register(CHAT, 16, name="آرش", city="کرمان", age=21,
                      nickname="Dark")
    profiles.buy(CHAT, 16, "badge_dragon")     # اول
    profiles.buy(CHAT, 16, "badge_fox")        # دوم
    title = profile_menu.build_title(profiles.get(CHAT, 16), User(16))
    check("اولین نشان انتخاب می‌شود، نه ارزان‌ترین",
          title == "🐉 Dark 🐉", f"-> {title!r}")
    check("first_badge هم همان را می‌دهد",
          profiles.first_badge(CHAT, 16)["id"] == "badge_dragon")


def test_star_rendering():
    print("\n### ⭐ نمایش ستاره‌ها")
    check("صفر ستاره", profile_menu.build_stars(0) == "☆☆☆☆☆☆☆")
    check("سه ستاره", profile_menu.build_stars(3) == "★★★☆☆☆☆")
    check("هفت ستاره", profile_menu.build_stars(7) == "★★★★★★★")
    check("بیش از حداکثر کلیپ می‌شود",
          profile_menu.build_stars(99) == "★★★★★★★")
    check("مقدار منفی امن است", profile_menu.build_stars(-3) == "☆☆☆☆☆☆☆")


# ===========================================================================
# ۳) 📦 لیست آیتم‌ها
# ===========================================================================
def test_items_list_contents():
    print("\n### 📦 محتوای لیست آیتم‌ها")
    fresh()
    text, spans = profile_menu.render_items()

    check("سرتیتر لیست هست", "📦 لیست آیتم‌ها" in text)
    check("بخش نشان‌ها هست", "🛡 نشان‌ها" in text)
    check("بخش خرید سطح هست", "⭐ خرید سطح" in text)
    check("بخش خرید لقب هست", "🏷 خرید لقب اختصاصی" in text)

    expected_badges = [
        ("🦊", "نشان روباه", "۱۰۰", "نقره"),
        ("🦁", "نشان شیر", "۱۲۰", "نقره"),
        ("🫀", "نشان قلب", "۳۰۰", "برنز"),
        ("👑", "نشان پادشاه", "۳۰۰", "نقره"),
        ("⚡", "نشان صاعقه", "۱۵۰", "نقره"),
        ("💀", "نشان اسکلت", "۲۰۰", "نقره"),
        ("🐺", "نشان گرگ", "۱۸۰", "نقره"),
        ("🐉", "نشان اژدها", "۵۰۰", "نقره"),
        ("☠️", "نشان افسانه", "۷۰۰", "نقره"),
        ("🌌", "نشان کهکشانی", "۹۰۰", "نقره"),
    ]
    for emoji, name, price, coin in expected_badges:
        check(f"«{name}» با قیمت درست",
              f"{emoji} {name} — {price} {coin}" in text)

    expected_stars = [
        ("⭐", "یک ستاره", "۲۰۰"), ("⭐⭐", "دو ستاره", "۴۰۰"),
        ("⭐⭐⭐", "سه ستاره", "۸۰۰"), ("⭐⭐⭐⭐", "چهار ستاره", "۱۰۰۰"),
        ("⭐⭐⭐⭐⭐", "پنج ستاره", "۱۲۰۰"),
        ("⭐⭐⭐⭐⭐⭐", "شش ستاره", "۱۴۰۰"),
        ("⭐⭐⭐⭐⭐⭐⭐", "هفت ستاره", "۱۸۰۰"),
    ]
    for stars, name, price in expected_stars:
        check(f"«{name}» با قیمت درست",
              f"{stars} {name} — {price} نقره" in text)

    expected_titles = [
        ("👑", "𝙁𝙤𝙭 𝙆𝙞𝙣𝙜"), ("⚡", "𝘿𝙖𝙧𝙠 𝙇𝙤𝙧𝙙"), ("💎", "𝙍𝙤𝙮𝙖𝙡"),
        ("🦊", "𝙁𝙤𝙭 𝘽𝙤𝙮"), ("☠️", "𝙆𝙞𝙡𝙡𝙚𝙧"), ("👑", "𝙊𝙫𝙚𝙧𝙇𝙤𝙧𝙙"),
        ("⚔️", "𝙒𝙖𝙧𝙧𝙞𝙤𝙧"), ("🌙", "𝙈𝙤𝙤𝙣"), ("😈", "𝘿𝙚𝙫𝙞𝙡"),
        ("💀", "𝙍𝙚𝙖𝙥𝙚𝙧"), ("🎭", "𝙋𝙝𝙖𝙣𝙩𝙤𝙢"), ("🐺", "𝙇𝙤𝙣𝙚 𝙒𝙤𝙡𝙛"),
        ("🐉", "𝘿𝙧𝙖𝙜𝙤𝙣"), ("⚜️", "𝙀𝙢𝙥𝙚𝙧𝙤𝙧"), ("🌠", "𝙎𝙩𝙖𝙧𝘽𝙤𝙮"),
    ]
    for emoji, title in expected_titles:
        check(f"لقب «{title}» هست", f"{emoji} {title}" in text)

    check("قیمت لقب‌ها اعلام شده", "قیمت همه لقب‌ها: ۲۰۰ برنز" in text)
    check("تعداد نشان‌ها ۱۰ است", len(catalog.badges()) == 10)
    check("تعداد سطح‌ها ۷ است", len(catalog.stars()) == 7)
    check("تعداد لقب‌ها ۱۵ است", len(catalog.titles()) == 15)


def test_items_list_is_fully_bold():
    print("\n### 📦 کل لیست آیتم‌ها Bold است")
    text, spans = profile_menu.render_items()
    from economy.ui.formatting import u16
    check("دقیقاً یک span پوششی", len(spans) == 1, f"-> {spans}")
    kind, offset, length = spans[0]
    check("نوع span از جنس bold است", kind == "bold")
    check("از ابتدای متن شروع می‌شود", offset == 0)
    check("تا انتهای متن ادامه دارد", length == u16(text),
          f"-> {length} != {u16(text)}")

    prompt, prompt_spans = profile_menu.buy_prompt()
    check("راهنمای خرید هم کاملاً Bold است",
          len(prompt_spans) == 1 and prompt_spans[0][1] == 0
          and prompt_spans[0][2] == u16(prompt))


def test_no_separate_section_for_items():
    print("\n### 📦 هیچ بخش جداگانه‌ای برای آیتم‌ها نیست")
    fresh()
    profiles.register(CHAT, 20, name="فرید", city="زنجان", age=26)

    async def scenario():
        bot = Bot()
        menu = Event()
        await send(bot, menu, 20, "پروفایل")
        return menu

    menu = asyncio.run(scenario())
    check("منو فقط سه گزینه + بستن دارد",
          menu.said("۱) 📦 لیست آیتم‌ها") and menu.said("۲) 🛍 خرید آیتم")
          and menu.said("۳) ✏️ ویرایش اطلاعات") and menu.said("۰) بستن"))
    check("منو گزینهٔ جداگانهٔ «نشان‌ها» ندارد",
          "۴)" not in menu.last)
    check("منو گزینهٔ جداگانهٔ «لقب» ندارد", "۵)" not in menu.last)

    # هیچ دستور مستقلی برای این سه دسته وجود ندارد.
    for command in ("نشان", "نشان‌ها", "لقب", "ستاره", "سطح"):
        check(f"«{command}» دستور مستقل نیست",
              not profile_menu.is_command(command))
    eco_handler.reset_all()


def test_item_numbering_is_stable():
    print("\n### 📦 شماره‌گذاری پایدار آیتم‌ها")
    items = catalog.all_items()
    check("۳۲ آیتم در مجموع", len(items) == 32, f"-> {len(items)}")
    check("شمارهٔ ۱ نشان روباه است", items[0]["id"] == "badge_fox")
    check("شمارهٔ ۱۱ یک ستاره است", items[10]["id"] == "star_1")
    check("شمارهٔ ۱۸ اولین لقب است", items[17]["id"] == "title_fox_king")
    check("resolve با عدد کار می‌کند",
          catalog.resolve("1")["id"] == "badge_fox")
    check("resolve با عدد فارسی کار می‌کند",
          catalog.resolve("۱۸")["id"] == "title_fox_king")
    check("resolve با شناسه کار می‌کند",
          catalog.resolve("badge_dragon")["id"] == "badge_dragon")
    check("resolve با نام فارسی کار می‌کند",
          catalog.resolve("نشان گرگ")["id"] == "badge_wolf")
    check("resolve با نام کوتاه کار می‌کند",
          catalog.resolve("گرگ")["id"] == "badge_wolf")
    check("عدد خارج از بازه None می‌دهد", catalog.resolve("99") is None)
    check("متن بی‌ربط None می‌دهد", catalog.resolve("سلام") is None)


# ===========================================================================
# اتصال خرید به اقتصاد
# ===========================================================================
def test_buy_deducts_real_coins():
    print("\n### 💰 خرید واقعاً از اقتصاد کسر می‌کند")
    fresh()
    fund(30, silver=500)
    profiles.register(CHAT, 30, name="پویا", city="بابل", age=23)

    before = economy.get_balance(CHAT, 30)[economy.SILVER]
    item, balance, profile = profiles.buy(CHAT, 30, "badge_fox")
    after = economy.get_balance(CHAT, 30)[economy.SILVER]

    check("۱۰۰ نقره کسر شد", before - after == 100, f"{before} -> {after}")
    check("موجودی برگشتی هم‌خوان است", balance[economy.SILVER] == after)
    check("نشان در پروفایل ثبت شد", "badge_fox" in profile["badges"])
    check("خرید در تاریخچهٔ اقتصاد ثبت شد",
          economy.transaction_history(CHAT, 30)[0]["kind"] == "purchase")
    check("ارزش کل بازمحاسبه شد",
          economy.get_balance(CHAT, 30)["total_coin_value"] == after * 10)


def test_buy_rejects_insufficient_balance():
    print("\n### 💰 موجودی ناکافی خرید را رد می‌کند")
    fresh()
    fund(31, silver=50)
    profiles.register(CHAT, 31, name="حمید", city="ساری", age=29)
    try:
        profiles.buy(CHAT, 31, "badge_fox")
        check("خرید بدون پول رد می‌شود", False)
    except profiles.ProfileError as error:
        check("خرید بدون پول رد می‌شود", "کافی نیست" in str(error))
    check("هیچ سکه‌ای کسر نشد",
          economy.get_balance(CHAT, 31)[economy.SILVER] == 50)
    check("هیچ نشانی ثبت نشد", profiles.get(CHAT, 31)["badges"] == [])


def test_buy_rejects_duplicate():
    print("\n### 💰 خرید تکراری رد می‌شود")
    fresh()
    fund(32, silver=500)
    profiles.register(CHAT, 32, name="زهرا", city="گرگان", age=26)
    profiles.buy(CHAT, 32, "badge_fox")
    balance_after_first = economy.get_balance(CHAT, 32)[economy.SILVER]
    try:
        profiles.buy(CHAT, 32, "badge_fox")
        check("نشان تکراری رد می‌شود", False)
    except profiles.ProfileError as error:
        check("نشان تکراری رد می‌شود", "قبلاً" in str(error))
    check("پول دوباره کسر نشد",
          economy.get_balance(CHAT, 32)[economy.SILVER]
          == balance_after_first)
    check("نشان دوبار ثبت نشد",
          profiles.get(CHAT, 32)["badges"].count("badge_fox") == 1)


def test_buy_is_idempotent_by_reference():
    print("\n### 💰 مرجع تکراری دوبار پول نمی‌گیرد")
    fresh()
    fund(33, silver=500)
    profiles.register(CHAT, 33, name="کاوه", city="اراک", age=35)
    profiles.buy(CHAT, 33, "badge_fox", reference="ref-1")
    first = economy.get_balance(CHAT, 33)[economy.SILVER]
    profiles.buy(CHAT, 33, "badge_lion", reference="ref-1")
    check("مرجع تکراری خرید دوم را بی‌اثر می‌کند",
          economy.get_balance(CHAT, 33)[economy.SILVER] == first)
    check("نشان دوم اضافه نشد",
          "badge_lion" not in profiles.get(CHAT, 33)["badges"])


def test_star_purchase_sets_level():
    print("\n### ⭐ خرید سطح، تعداد ستاره را تنظیم می‌کند")
    fresh()
    fund(34, silver=5000)
    profiles.register(CHAT, 34, name="نگار", city="قزوین", age=22)
    profiles.buy(CHAT, 34, "star_3")
    check("سطح روی ۳ نشست", profiles.stars(CHAT, 34) == 3)
    text, _ = profile_menu.render_card(CHAT, 34, User(34))
    check("کارت سه ستاره نشان می‌دهد", "⭐ سطح: ★★★☆☆☆☆" in text)

    profiles.buy(CHAT, 34, "star_5")
    check("ارتقا به سطح بالاتر ممکن است", profiles.stars(CHAT, 34) == 5)
    try:
        profiles.buy(CHAT, 34, "star_2")
        check("سطح پایین‌تر دوباره فروخته نمی‌شود", False)
    except profiles.ProfileError:
        check("سطح پایین‌تر دوباره فروخته نمی‌شود", True)


def test_title_purchase_applies_immediately():
    print("\n### 🏷 خرید لقب فوراً اعمال می‌شود")
    fresh()
    fund(35, bronze=2000, silver=2000)
    profiles.register(CHAT, 35, name="سینا", city="بوشهر", age=24)
    profiles.buy(CHAT, 35, "badge_bolt")
    before = economy.get_balance(CHAT, 35)[economy.BRONZE]
    profiles.buy(CHAT, 35, "title_dark_lord")
    after = economy.get_balance(CHAT, 35)[economy.BRONZE]

    check("۲۰۰ برنز کسر شد", before - after == 200)
    profile = profiles.get(CHAT, 35)
    check("لقب روی پروفایل نشست", profile["nickname"] == "𝘿𝙖𝙧𝙠 𝙇𝙤𝙧𝙙")
    text, _ = profile_menu.render_card(CHAT, 35, User(35))
    check("لقب در کارت دیده می‌شود", "🏷 لقب: 𝘿𝙖𝙧𝙠 𝙇𝙤𝙧𝙙" in text)
    check("عنوان کادر هم به‌روز شد", "⚡ 𝘿𝙖𝙧𝙠 𝙇𝙤𝙧𝙙 ⚡" in text)


def test_all_items_are_purchasable():
    print("\n### 💰 هر ۳۲ آیتم واقعاً خریدنی است")
    fresh()
    fund(36, bronze=100000, silver=100000, gold=1000)
    profiles.register(CHAT, 36, name="تست", city="تهران", age=30)
    bought = 0
    for item in catalog.all_items():
        if item["kind"] == catalog.KIND_STAR and \
                profiles.stars(CHAT, 36) >= item["level"]:
            continue
        try:
            profiles.buy(CHAT, 36, item["id"])
            bought += 1
        except profiles.ProfileError as error:
            check(f"خرید {item['id']} بدون خطا", False, f"-> {error}")
    check("همهٔ آیتم‌ها بدون خطا خریداری شدند", bought >= 30, f"-> {bought}")
    profile = profiles.get(CHAT, 36)
    check("همهٔ نشان‌ها ثبت شدند", len(profile["badges"]) == 10)
    check("همهٔ لقب‌ها ثبت شدند", len(profile["titles"]) == 15)
    check("سطح روی حداکثر است", profile["stars"] == 7)


# ===========================================================================
# نمایش فوری پس از خرید — از مسیر هندلر
# ===========================================================================
def test_buy_through_handler_shows_immediately():
    print("\n### 🔌 خرید از منو و نمایش فوری در کارت")
    fresh()
    fund(40, silver=3000)
    profiles.register(CHAT, 40, name="آرمان", city="سنندج", age=27)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 40, "پروفایل")
        listing = Event()
        await send(bot, listing, 40, "1")
        prompt = Event()
        await send(bot, prompt, 40, "2")
        buy = Event()
        await send(bot, buy, 40, "1")            # نشان روباه
        card = Event()
        await send(bot, card, 40, "پروفایل")
        return bot, listing, prompt, buy, card

    bot, listing, prompt, buy, card = asyncio.run(scenario())
    check("لیست آیتم‌ها نمایش داده شد", listing.said("📦 لیست آیتم‌ها"))
    check("لیست کاملاً Bold ارسال شد", listing.entity_counts[-1] == 1)
    check("راهنمای خرید آمد", prompt.said("برای خرید، شمارهٔ آیتم"))
    check("خرید موفق بود", buy.said("خریداری شد"))
    check("اثر آیتم اعلام شد", buy.said("به پروفایل شما اضافه شد"))
    check("نشان فوراً در کارت دیده می‌شود", card.said("🦊"))
    check("سکه کسر شد",
          economy.get_balance(CHAT, 40)[economy.SILVER] == 2900)
    check("خرید لاگ شد", bot.logger.has("PROFILE BUY"))
    eco_handler.reset_all()


def test_buy_star_and_title_through_handler():
    print("\n### 🔌 خرید سطح و لقب از منو")
    fresh()
    fund(41, bronze=3000, silver=6000)
    profiles.register(CHAT, 41, name="لیلا", city="همدان", age=31)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 41, "پروفایل")
        await send(bot, Event(), 41, "2")
        star = Event()
        await send(bot, star, 41, "13")          # سه ستاره
        await send(bot, Event(), 41, "2")
        title = Event()
        await send(bot, title, 41, "18")         # Fox King
        card = Event()
        await send(bot, card, 41, "پروفایل")
        return star, title, card

    star, title, card = asyncio.run(scenario())
    check("خرید سطح موفق بود", star.said("خریداری شد"))
    check("ستاره‌های جدید اعلام شد", star.said("★★★☆☆☆☆"))
    check("خرید لقب موفق بود", title.said("خریداری شد"))
    check("لقب جدید اعلام شد", title.said("𝙁𝙤𝙭 𝙆𝙞𝙣𝙜"))
    check("سطح در کارت دیده می‌شود", card.said("⭐ سطح: ★★★☆☆☆☆"))
    check("لقب در کارت دیده می‌شود", card.said("🏷 لقب: 𝙁𝙤𝙭 𝙆𝙞𝙣𝙜"))
    check("برنز لقب کسر شد",
          economy.get_balance(CHAT, 41)[economy.BRONZE] == 2800)
    check("نقرهٔ سطح کسر شد",
          economy.get_balance(CHAT, 41)[economy.SILVER] == 5200)
    eco_handler.reset_all()


def test_buy_failure_message_through_handler():
    print("\n### 🔌 پیام خطای خرید از منو")
    fresh()
    fund(42, silver=10)
    profiles.register(CHAT, 42, name="بهنام", city="یاسوج", age=20)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 42, "پروفایل")
        await send(bot, Event(), 42, "2")
        poor = Event()
        await send(bot, poor, 42, "1")
        unknown = Event()
        await send(bot, unknown, 42, "999")
        cancel = Event()
        await send(bot, cancel, 42, "0")
        return poor, unknown, cancel

    poor, unknown, cancel = asyncio.run(scenario())
    check("کمبود موجودی اعلام می‌شود", poor.said("کافی نیست"))
    check("آیتم ناشناخته اعلام می‌شود", unknown.said("در فهرست نیست"))
    check("لغو کار می‌کند", cancel.said("لغو شد"))
    check("پول دست‌نخورده ماند",
          economy.get_balance(CHAT, 42)[economy.SILVER] == 10)
    eco_handler.reset_all()


# ===========================================================================
# ویرایش
# ===========================================================================
def test_edit_flow():
    print("\n### ✏️ ویرایش اطلاعات")
    fresh()
    profiles.register(CHAT, 50, name="امیر", city="کاشان", age=24)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 50, "پروفایل")
        menu = Event()
        await send(bot, menu, 50, "3")
        prompt = Event()
        await send(bot, prompt, 50, "2")
        done = Event()
        await send(bot, done, 50, "اصفهان")
        return menu, prompt, done

    menu, prompt, done = asyncio.run(scenario())
    check("منوی ویرایش باز شد", menu.said("✏️ ویرایش اطلاعات"))
    check("مقدار جدید خواسته شد", prompt.said("مقدار جدید"))
    check("ذخیره تأیید شد", done.said("ذخیره شد"))
    check("شهر عوض شد", profiles.get(CHAT, 50)["city"] == "اصفهان")
    check("بقیهٔ فیلدها دست‌نخورده", profiles.get(CHAT, 50)["name"] == "امیر")
    check("کارت به‌روز نمایش داده شد", done.said("📍 شهر: اصفهان"))
    eco_handler.reset_all()


# ===========================================================================
# ماندگاری
# ===========================================================================
def test_persistence_across_reload():
    print("\n### 💾 ماندگاری دائمی روی دیسک")
    temp = fresh()
    fund(60, silver=3000, bronze=3000)
    profiles.register(CHAT, 60, name="شادی", city="ارومیه", age=23)
    profiles.buy(CHAT, 60, "badge_galaxy")
    profiles.buy(CHAT, 60, "star_4")
    profiles.buy(CHAT, 60, "title_royal")

    # شبیه‌سازی راه‌اندازی دوبارهٔ ربات: کش پاک، فایل همان.
    storage._cache = None
    storage._cache_mtime = None

    profile = profiles.get(CHAT, 60)
    check("اطلاعات پس از ریست کش سرجایش است", profile["name"] == "شادی")
    check("شهر ماند", profile["city"] == "ارومیه")
    check("سن ماند", profile["age"] == 23)
    check("نشان ماند", profile["badges"] == ["badge_galaxy"])
    check("ستاره ماند", profile["stars"] == 4)
    check("لقب ماند", profile["nickname"] == "𝙍𝙤𝙮𝙖𝙡")
    check("فایل واقعاً روی دیسک است",
          (temp / "economy.json").exists())


def test_profile_does_not_break_wallet():
    print("\n### 💾 پروفایل کیف پول را خراب نمی‌کند")
    fresh()
    fund(61, bronze=250, silver=30, gold=1)
    before = economy.get_balance(CHAT, 61)
    profiles.register(CHAT, 61, name="مهدی", city="خرم‌آباد", age=28)
    after = economy.get_balance(CHAT, 61)
    check("ثبت پروفایل موجودی را عوض نمی‌کند", before == after)
    check("ارزش کل درست ماند", after["total_coin_value"] == 250 + 300 + 100)
    check("رتبه‌بندی سالم است", economy.get_rank(CHAT, 61) == 1)


# ===========================================================================
# هیچ قابلیتی حذف نشده
# ===========================================================================
def test_existing_sections_still_work():
    print("\n### 🔒 «موجودی» و «فروشگاه» دست‌نخورده‌اند")
    fresh()
    fund(70, bronze=300)

    async def scenario():
        bot = Bot()
        balance = Event()
        await send(bot, balance, 70, "موجودی")
        shop = Event()
        await send(bot, shop, 70, "فروشگاه")
        return balance, shop

    balance, shop = asyncio.run(scenario())
    check("منوی موجودی باز می‌شود", balance.said("💰 کیف پول شما"))
    check("گزینه‌های موجودی سرجایشان‌اند",
          all(balance.said(part) for part in
              ("تبدیل برنز به نقره", "تبدیل نقره به طلا", "انتقال برنز",
               "تاریخچه", "جایزه روزانه")))
    check("منوی فروشگاه باز می‌شود", shop.said("🛒 فروشگاه"))
    check("گزینه‌های فروشگاه سرجایشان‌اند",
          shop.said("لیست آیتم‌ها") and shop.said("خرید"))
    eco_handler.reset_all()


def test_sections_do_not_collide():
    print("\n### 🔒 سه بخش با هم تداخل ندارند")
    fresh()
    profiles.register(CHAT, 71, name="کیان", city="نور", age=25)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 71, "پروفایل")
        opened_profile = profile_menu.is_open(CHAT, 71)
        await send(bot, Event(), 71, "موجودی")
        after_balance = (profile_menu.is_open(CHAT, 71),
                         balance_menu.is_open(CHAT, 71))
        await send(bot, Event(), 71, "فروشگاه")
        after_shop = (balance_menu.is_open(CHAT, 71),
                      shop_menu.is_open(CHAT, 71))
        await send(bot, Event(), 71, "پروفایل")
        after_profile = (shop_menu.is_open(CHAT, 71),
                         profile_menu.is_open(CHAT, 71))
        return opened_profile, after_balance, after_shop, after_profile

    opened, after_balance, after_shop, after_profile = asyncio.run(scenario())
    check("پروفایل session باز می‌کند", opened)
    check("«موجودی» session پروفایل را می‌بندد", after_balance == (False, True))
    check("«فروشگاه» session موجودی را می‌بندد", after_shop == (False, True))
    check("«پروفایل» session فروشگاه را می‌بندد",
          after_profile == (False, True))
    eco_handler.reset_all()


def test_unrelated_text_is_not_consumed():
    print("\n### 🔒 پیام عادی داخل منو مصرف نمی‌شود")
    fresh()
    profiles.register(CHAT, 72, name="بابک", city="آمل", age=32)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 72, "پروفایل")
        chat = Event()
        consumed = await send(bot, chat, 72, "سلام بچه‌ها")
        return consumed, chat

    consumed, chat = asyncio.run(scenario())
    check("گپ عادی مصرف نمی‌شود", consumed is False)
    check("ربات به گپ عادی جواب نمی‌دهد", not chat.replies)
    check("منو باز می‌ماند", profile_menu.is_open(CHAT, 72))
    eco_handler.reset_all()


def test_close_menu():
    print("\n### 🔒 بستن منو")
    fresh()
    profiles.register(CHAT, 73, name="نازنین", city="کرمانشاه", age=21)

    async def scenario():
        bot = Bot()
        await send(bot, Event(), 73, "پروفایل")
        close = Event()
        await send(bot, close, 73, "0")
        return close, profile_menu.is_open(CHAT, 73)

    close, still_open = asyncio.run(scenario())
    check("پیام بسته شدن آمد", close.said("بسته شد"))
    check("session بسته شد", not still_open)
    eco_handler.reset_all()


# ===========================================================================
# استقلال ماژول
# ===========================================================================
def test_independence():
    print("\n### 🔒 پروفایل هیچ ماژول بازی/ربات را import نمی‌کند")
    import ast

    imported = set()
    for path in (ROOT / "economy" / "profiles.py",
                 ROOT / "economy" / "catalog.py",
                 ROOT / "economy" / "ui" / "profile_menu.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

    forbidden = {"modules", "handlers", "core", "splusthon"}
    leaked = imported & forbidden
    check("هیچ وابستگی ممنوعی ندارد", not leaked, f"-> {sorted(leaked)}")
    check("فقط economy و کتابخانهٔ استاندارد",
          imported <= {"economy", "datetime", "time", "json", "os",
                       "pathlib", "tempfile"},
          f"-> {sorted(imported)}")


def test_corrupt_profile_is_survivable():
    print("\n### 🛡 دادهٔ خراب باعث کرش نمی‌شود")
    fresh()
    import economy.coins.accounts as accounts
    with storage.transaction() as data:
        user = accounts._user(data, accounts.user_key(CHAT, 80))
        user["profile"] = {"badges": "نه لیست", "stars": "سه"}

    profile = profiles.get(CHAT, 80)
    check("badges به لیست خالی برمی‌گردد", profile["badges"] == [])
    check("stars به صفر برمی‌گردد", profile["stars"] == 0)
    text, _ = profile_menu.render_card(CHAT, 80, User(80))
    check("کارت بدون کرش ساخته می‌شود", "👤 نام:" in text)
    check("عنوان بدون ایموجی ساخته می‌شود",
          profile_menu.build_title(profile, User(80, "علی")) == "علی")


def test_card_without_registration():
    print("\n### 🛡 کارت برای کاربر ثبت‌نشده هم امن است")
    fresh()
    text, _ = profile_menu.render_card(CHAT, 81, User(81, "ناشناس"))
    check("نام از حساب گرفته می‌شود", "👤 نام: ناشناس" in text)
    check("شهر خالی با خط تیره", "📍 شهر: —" in text)
    check("سن خالی با خط تیره", "🎂 سن: —" in text)
    check("نشان‌ها «ندارد»", "🛡 نشان‌ها:\nندارد" in text)
    check("خط لقب وقتی لقب نیست حذف می‌شود", "🏷 لقب:" not in text)


# ===========================================================================
def main():
    test_registration_flow()
    test_registration_optional_nickname()
    test_registration_validation()
    test_second_time_shows_card_directly()
    test_profile_is_per_group()
    test_card_layout_matches_sample()
    test_card_keeps_all_fields()
    test_numbers_have_no_thousand_separator()
    test_title_rules()
    test_title_without_any_badge()
    test_title_uses_first_bought_badge()
    test_star_rendering()
    test_items_list_contents()
    test_items_list_is_fully_bold()
    test_no_separate_section_for_items()
    test_item_numbering_is_stable()
    test_buy_deducts_real_coins()
    test_buy_rejects_insufficient_balance()
    test_buy_rejects_duplicate()
    test_buy_is_idempotent_by_reference()
    test_star_purchase_sets_level()
    test_title_purchase_applies_immediately()
    test_all_items_are_purchasable()
    test_buy_through_handler_shows_immediately()
    test_buy_star_and_title_through_handler()
    test_buy_failure_message_through_handler()
    test_edit_flow()
    test_persistence_across_reload()
    test_profile_does_not_break_wallet()
    test_existing_sections_still_work()
    test_sections_do_not_collide()
    test_unrelated_text_is_not_consumed()
    test_close_menu()
    test_independence()
    test_corrupt_profile_is_survivable()
    test_card_without_registration()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
