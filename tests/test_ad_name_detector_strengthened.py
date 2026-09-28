# -*- coding: utf-8 -*-
"""تقویت تشخیص «نام تبلیغاتی» در برابر دور زدن (modules/ad_name_detector).

پوشش: کلمات دقیق، فاصله‌دار، کشیده، تکرار حروف، شکل‌های شکسته (نیم‌فاصله/
نقطه/زیرخط)، جانشینی حروف، لاتین/Unicode مشابه، ایموجی‌ها، ترکیب چند کلمه،
و نام‌های کاملاً مجاز برای اطمینان از نبودِ false positive.

اجرا مستقیم: ``python3 tests/test_ad_name_detector_strengthened.py``
و با pytest هم سازگار است.
"""
import os
import sys
import tempfile
import traceback
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.environ.setdefault(
    "SOROUSH_BOT_DATA_DIR", tempfile.mkdtemp(prefix="ad-name-detector-test-"))

from modules import ad_name_detector as det  # noqa: E402


def _user(name, username=None, last_name=None):
    return SimpleNamespace(first_name=name, last_name=last_name, username=username)


def _hit(name, username=None, last_name=None):
    return det.reason(_user(name, username, last_name))


# ۱) کلمات دقیق — همهٔ موارد تازه + نمونه‌های قبلی برای حفظ رفتار
def test_exact_words():
    for name in (
        "سکس", "بیوگرافی", "فیلم", "زوری", "کانال", "گروه",
        "یکی بیاد", "خانوم", "پسر", "دختر",
        "پیوی", "خاله راضی", "فیلترشکن قوی",
    ):
        reason = _hit(name)
        assert reason is not None, f"exact word missed: {name!r}"


# ۲) کلمات با فاصلهٔ معمولی یا غیرعادی بین حروف
def test_spaced_letters():
    for name in (
        "س ک س", "بیو گرا فی", "د خ ت ر", "ک ا ن ا ل",
        "خ ا ن وم", "گ ر وه", "ز و ر ی", "ی ک ی   ب ی ا د", "پ س ر",
    ):
        reason = _hit(name)
        assert reason is not None, f"spaced form missed: {name!r}"


# ۳) کلمات کشیده با «ـ»
def test_stretched_words():
    for name in (
        "ســکــس", "بیـــوگرافی", "دختـــر", "کاناااال",
        "خانـــوم", "گروههــ", "زورییـــ",
    ):
        reason = _hit(name)
        assert reason is not None, f"stretched form missed: {name!r}"


# ۴) تکرار حروف
def test_repeated_letters():
    for name in (
        "سکسس", "سسکس", "دختترر", "پسسر", "خانوووم",
        "گرووهه", "زوریی", "یکی بیادد", "بیوگرافیی",
    ):
        reason = _hit(name)
        assert reason is not None, f"repeated-letters form missed: {name!r}"


# ۵) شکل‌های شکسته: نیم‌فاصله، نقطه، زیرخط، اسلش، ستاره، ترکیب‌ها
def test_broken_words():
    for name in (
        "س‌ک‌س", "س.ک.س", "س_ک_س", "س/ک/س", "س*ک*س", "س|ک|س",
        "بیو‌گرافی", "بیو.گرافی", "ک.ا.ن.ا.ل", "د خ.ت ر",
    ):
        reason = _hit(name)
        assert reason is not None, f"broken form missed: {name!r}"


# ۶) جانشینی حروف و شکل‌های رایجِ دورزدن برای سکس/بیوگرافی
def test_substitution_forms():
    for name in (
        "ثکث", "سکث", "ثکس", "س۶س", "س6س", "سkس",
        "بیوکرافی", "بیوقرافی", "بیوگراف", "بیوگرفی",
        "sex", "sexx", "Sexy", "s e x", "biography", "bioGraphi",
    ):
        reason = _hit(name)
        assert reason is not None, f"substitution form missed: {name!r}"


def test_unicode_lookalikes():
    # حروف عربی (ي/ك) و حروف ریاضی 𝔘𝔫𝔦𝔠𝔬𝔡𝔢 (NFKC)
    for name in ("سکس ي چکم", "بيوگرافي", "فیلترشکن ي"):
        reason = _hit(name)
        assert reason is not None, f"arabic-lookalike missed: {name!r}"
    reason = det.reason(_user("𝕤𝕖𝕩"))
    assert reason is not None, "math-alphanumeric sex missed"


# ۷) ایموجی‌های تبلیغاتی — تک، تکراری، و وسط نام واقعی
def test_emojis():
    for name in (
        "💦", "🌈", "👄", "💋", "🤤", "😰", "🥵", "🍑", "🔞",
        "لیلا 💦", "🌈🌈🌈", "🍑 داغه", "🥵🥵 شب",
    ):
        reason = _hit(name)
        assert reason is not None, f"emoji missed: {name!r}"


# ۸) ترکیب چند کلمه/ایموجی
def test_combined_names():
    for name in (
        "💋 دختر سکسی 💦",
        "خانوم بیوگرافی چک",
        "پسر گرم 🍑 کانال",
        "گروه دخترا",
    ):
        reason = _hit(name)
        assert reason is not None, f"combined name missed: {name!r}"


# ۹) نام کاربری (آیدی) هم بررسی می‌شود
def test_username_checked():
    assert det.reason(_user("کاربر عادی", username="sexy_channel2")) is not None
    assert det.reason(_user("کاربر عادی", username="vpn★seller")) is not None
    assert det.reason(_user("کاربر", username="ali_rezaei")) is None


# ۱۰) نام‌های مجاز — هیچ false positive
def test_legitimate_names_not_flagged():
    for name, last, username in (
        ("علی", "رضایی", "ali_rezaei"),
        ("محمد", "حسینی", "m_hosseini"),
        ("سارا", "احمدی", None),
        ("رضا", "پیروز", None),
        ("پرستو", None, None),          # «پسر» نباید داخل پرستو گرفته شود
        ("خانم", None, None),           # «خانوم» با خانم فرق دارد
        ("گروهبان", None, None),        # استثنای گروه‌بان
        ("گروه‌بان", None, None),
        ("بیوکرافت", None, None),       # minecraft-like name
        ("کاوه", None, None),
        ("گلنار", None, None),
        ("میلاد", None, None),
        ("فاطمه", "زهرا", None),
        ("مریم", "صالحی", None),
        ("امیرحسین", "شفیعی", None),
        ("نرگس", "محمدی", None),
        ("سپیده", None, None),
        ("زهرا", "کاظمی", "zahra_k"),
    ):
        reason = det.reason(_user(name, username, last))
        assert reason is None, f"false positive: {name!r} ({last!r}) -> {reason!r}"


def test_display_name_unchanged():
    shown = det.display_name(_user("سارا", "ali_s", None))
    assert shown == "@ali_s"


def _run_all():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            traceback.print_exc()
            print(f"FAIL {name}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
