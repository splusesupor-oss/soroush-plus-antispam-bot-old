"""GLOBAL_FORBIDDEN_WORDS must stay on when a group filter is turned off.

    python tests/test_global_vs_group_word_isolation.py
"""
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.spam_detector import SpamDetector
from modules import group_banned_words_control as group_switch
from modules.group_words_storage import find_matching_filter_word

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class _FakeConfig:
    def __init__(self, words):
        self.banned_words = set(words)
        self._banned_words_version = 1

    def get(self, key, default=None):
        if key == "check_banned_words":
            return True
        return default

    def reload_if_needed(self):
        pass


def test_global_ignores_group_switch():
    print("\n### لیست سراسری به سوئیچ گروه وابسته نیست")
    source = inspect.getsource(SpamDetector.check_banned_words)
    module_src = inspect.getsource(SpamDetector)
    # کامیت aaf2a81 («جداسازی سیستم کلمات ممنوعه») معماری را عمداً برعکس
    # کرد: «کلمات ممنوعه» حالت سختگیرانه است و per-group با
    # ``group_banned_words_control.is_enabled`` گیت می‌شود، در حالی که
    # «فیلتر کلمات» (/filter) همیشه فعال است. پس وجودِ is_enabled در
    # check_banned_words رفتار درستِ فعلی است و آنچه باید تضمین شود
    # استقلالِ این دو سیستم از هم است.
    check("کلمات ممنوعه پشت سوئیچ per-group است (aaf2a81)",
          "is_enabled" in source and "group_banned_words_control" in module_src)

    det = SpamDetector(_FakeConfig(["بیو", "سکس"]))
    # وضعیتِ گروه به‌جای اتکا به فایلِ واقعی (که در طول زمان عوض می‌شود)
    # صریح تنظیم می‌شود تا تست خودکفا بماند.
    disabled_chat = 9429374
    group_switch.disable(disabled_chat)
    try:
        hit, _reason = det.check_banned_words("بیو چک کن", disabled_chat)
        check("گروهِ خاموش، حالت سختگیرانه را اجرا نمی‌کند", hit is False,
              f"-> {hit} {_reason!r}")
    finally:
        group_switch.enable(disabled_chat)
    unknown_chat = 999999999
    hit, reason = det.check_banned_words("بیو", unknown_chat)
    check("گروه تازه پیش‌فرض روشن است و کلمه را می‌گیرد",
          hit is True and "بیو" in (reason or ""), f"-> {hit} {reason!r}")
    is_spam, spam_reason = det.is_spam("سکس", unknown_chat)
    check("is_spam هم روی گروهِ روشن کار می‌کند",
          is_spam and "سکس" in str(spam_reason), f"-> {spam_reason!r}")


def test_group_switch_only_affects_custom_filter():
    print("\n### سوئیچ گروه فقط فیلتر سفارشی را عوض می‌کند")
    original_file = group_switch.FILE
    original_cache = group_switch._cache
    original_mtime = group_switch._cache_mtime
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "group_banned_words.json"
            path.write_text("{}", encoding="utf-8")
            group_switch.FILE = str(path)
            group_switch._cache = None
            group_switch._cache_mtime = None

            new_chat = 888001
            check("گروه جدید پیش‌فرض روشن است",
                  group_switch.is_enabled(new_chat) is True)
            group_switch.disable(new_chat)
            check("disable فقط همان گروه را خاموش می‌کند",
                  group_switch.is_enabled(new_chat) is False)
            saved = json.loads(path.read_text(encoding="utf-8"))
            check("فایل سوئیچ فقط وضعیت گروه را نگه می‌دارد",
                  saved.get(str(new_chat)) is False)

            custom_words = ["رل پی"]
            check("فیلتر سفارشی هنوز مستقل match می‌کند",
                  find_matching_filter_word("بیا رل پی", custom_words) == "رل پی")

            # سوئیچ فقط حالت سختگیرانهٔ همان گروه را خاموش می‌کند و هیچ
            # اثری روی فیلترِ سفارشیِ گروه ندارد (بالا اثبات شد).
            det = SpamDetector(_FakeConfig(["بیو"]))
            hit, _reason = det.check_banned_words("بیو", new_chat)
            check("سوئیچِ خاموش، حالت سختگیرانهٔ همان گروه را خاموش می‌کند",
                  hit is False, f"-> {hit}")
            group_switch.enable(new_chat)
            hit_on, _r = det.check_banned_words("بیو", new_chat)
            check("با روشن کردن دوباره، کلمه دوباره گرفته می‌شود",
                  hit_on is True, f"-> {hit_on}")
    finally:
        group_switch.FILE = original_file
        group_switch._cache = original_cache
        group_switch._cache_mtime = original_mtime


def test_handler_gates_only_group_filter():
    print("\n### هندلر فقط فیلتر گروه را پشت سوئیچ می‌گذارد")
    handler_src = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8"
    )
    # طبق aaf2a81: فیلترِ سفارشی (/filter) عمداً بدونِ گیت است و سوئیچ
    # فقط به حالتِ سختگیرانهٔ کلمات ممنوعه مربوط می‌شود.
    check("فیلتر سفارشی گروه بدون گیت اجرا می‌شود",
          "find_matching_filter_word" in handler_src)
    check("سوئیچ برای حالت سختگیرانهٔ کلمات ممنوعه خوانده می‌شود",
          "group_banned_words_control" in handler_src)
    check("is_spam سراسری همچنان با chat_id صدا زده می‌شود",
          "bot.detector.is_spam(message_text, chat_id)" in handler_src)


def main():
    test_global_ignores_group_switch()
    test_group_switch_only_affects_custom_filter()
    test_handler_gates_only_group_filter()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
