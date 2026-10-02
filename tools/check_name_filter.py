#!/usr/bin/env python3
"""🔎 عیب‌یابی «فیلتر اسم» روی همان سروری که ربات اجرا می‌شود.

کد در تست end-to-end سبز است، پس اگر در گروه کار نمی‌کند یکی از این
چهار چیز است و همین اسکریپت دقیقاً می‌گوید کدام:

    ۱. نسخهٔ روی دیسک قدیمی است (pull نشده)
    ۲. پروسهٔ در حال اجرا از پوشهٔ دیگری بالا آمده یا restart نشده
    ۳. اسم اصلاً در فایل فیلتر این گروه ذخیره نشده
    ۴. خودِ تطبیق نام با آن اسم نمی‌خورد

    python tools/check_name_filter.py
    python tools/check_name_filter.py -1001234567890 "حسین"
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
problems = []


def ok(msg):
    print(f"  {GREEN}✔{OFF} {msg}")


def bad(msg, fix):
    print(f"  {RED}✘{OFF} {msg}")
    print(f"      {YELLOW}→ {fix}{OFF}")
    problems.append(msg)


def run(*args):
    try:
        return subprocess.run(
            args, cwd=str(ROOT), capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except Exception:
        return ""


print("=" * 64)
print("🔎 عیب‌یابی فیلتر اسم")
print("=" * 64)
print(f"پوشهٔ این نسخه: {ROOT}")

# ── ۱. نسخهٔ کد روی دیسک ───────────────────────────────────────────────
print("\n1️⃣  نسخهٔ کد روی دیسک")
head = run("git", "rev-parse", "--short", "HEAD")
print(f"  HEAD = {head or 'نامشخص'}")
handler_src = (ROOT / "handlers" / "message_handler.py").read_text(
    encoding="utf-8", errors="ignore"
)
has_gate = "_nf_term = _name_filter_hit(" in handler_src
has_enforce = "async def _enforce_ad_name" in handler_src
if has_gate and has_enforce:
    ok("گیت فیلتر اسم و تابع enforcement در کد هست")
else:
    bad(
        "کد روی دیسک قدیمی است (گیت فیلتر اسم وجود ندارد)",
        "git pull origin main",
    )

dirty = run("git", "status", "--short", "handlers/message_handler.py")
if dirty:
    bad(
        f"فایل handler دست‌کاری شده: {dirty}",
        "git checkout -- handlers/message_handler.py && git pull origin main",
    )

# ── ۲. پروسهٔ در حال اجرا ──────────────────────────────────────────────
print("\n2️⃣  پروسهٔ در حال اجرای ربات")
found_any = False
for pid_dir in sorted(Path("/proc").glob("[0-9]*")):
    try:
        cmdline = (pid_dir / "cmdline").read_bytes().decode(
            "utf-8", "ignore"
        ).replace("\x00", " ").strip()
    except Exception:
        continue
    if "python" not in cmdline or "main.py" not in cmdline:
        continue
    if "check_name_filter" in cmdline:
        continue
    found_any = True
    try:
        cwd = os.readlink(str(pid_dir / "cwd"))
    except Exception:
        cwd = "?"
    print(f"  pid={pid_dir.name}  cwd={cwd}")
    print(f"           cmd={cmdline[:90]}")
    if Path(cwd).resolve() != ROOT.resolve():
        bad(
            f"ربات از پوشهٔ دیگری اجرا می‌شود: {cwd}",
            f"آن پوشه را هم pull کن، یا ربات را از {ROOT} اجرا کن",
        )
    else:
        live = Path(cwd) / "handlers" / "message_handler.py"
        try:
            if "_nf_term = _name_filter_hit(" not in live.read_text(
                encoding="utf-8", errors="ignore"
            ):
                bad(
                    "پروسه از فایل قدیمی بالا آمده",
                    "bash restart_bot.sh",
                )
            else:
                ok("پروسه از همین پوشه اجرا می‌شود")
                print(f"      {YELLOW}⚠ اگر بعد از pull ری‌استارت نکرده‌ای،"
                      f" کد قدیمی هنوز در حافظه است → bash restart_bot.sh{OFF}")
        except Exception:
            pass
if not found_any:
    print(f"  {YELLOW}⚠{OFF} هیچ پروسهٔ main.py پیدا نشد — ربات خاموش است؟")

# ── ۳. محتوای فایل فیلترها ────────────────────────────────────────────
print("\n3️⃣  فیلترهای ذخیره‌شده")
try:
    from modules import name_filters
    from modules.group_id import normalize_group_id

    name_filters.reset_cache()
    print(f"  فایل: {name_filters.FILE}")
    if not Path(name_filters.FILE).exists():
        bad(
            "فایل فیلترها وجود ندارد — هیچ اسمی ذخیره نشده",
            "در گروه بنویس: فیلتر اسم حسین",
        )
        data = {}
    else:
        data = name_filters._load()
        if not data:
            bad("فایل خالی است", "در گروه بنویس: فیلتر اسم حسین")
        for group_key, items in data.items():
            terms = ", ".join(str(i.get("term")) for i in items)
            print(f"  گروه {group_key}: {terms or '—'}")
except Exception as error:
    bad(f"خواندن فیلترها شکست خورد: {error!r}", "لاگ را بفرست")
    data = {}

# ── ۴. تطبیق واقعی ────────────────────────────────────────────────────
print("\n4️⃣  آزمون تطبیق")
chat_arg = sys.argv[1] if len(sys.argv) > 1 else None
name_arg = sys.argv[2] if len(sys.argv) > 2 else None

if chat_arg and name_arg:
    pairs = [(chat_arg, name_arg)]
else:
    pairs = []
    for group_key, items in (data or {}).items():
        for item in items:
            pairs.append((group_key, str(item.get("term"))))
    if not pairs:
        print("  چیزی برای آزمون نیست.")
        print("  برای آزمون دستی:")
        print('    python tools/check_name_filter.py -100... "حسین"')

for group_key, display_name in pairs:
    class _FakeUser:
        id = 999999
        first_name = display_name
        last_name = None
        username = None

    try:
        matched = name_filters.match_name(group_key, _FakeUser)
    except Exception as error:
        matched = f"ERROR {error!r}"
    key = normalize_group_id(group_key)
    if matched and not str(matched).startswith("ERROR"):
        ok(f"گروه {key}: کاربری با نام «{display_name}» "
           f"→ فیلتر «{matched}» می‌خورد ✅")
    else:
        bad(
            f"گروه {key}: نام «{display_name}» با هیچ فیلتری نخورد ({matched})",
            "اسم را دقیقاً همان‌طور که در پروفایل کاربر است فیلتر کن",
        )

    try:
        from modules import ad_name_detector
        reason = ad_name_detector.reason(_FakeUser, group_key)
        if reason:
            ok(f"سیستم فیلتر تبلیغات هم همین را می‌گیرد: {reason}")
        else:
            bad(
                "ad_name_detector.reason() چیزی برنگرداند "
                "— اتصال فیلتر اسم به سیستم تبلیغات قطع است",
                "git pull origin main",
            )
    except Exception as error:
        bad(f"ad_name_detector شکست خورد: {error!r}", "لاگ را بفرست")

# ── جمع‌بندی ──────────────────────────────────────────────────────────
print("\n" + "=" * 64)
if problems:
    print(f"{RED}{len(problems)} مشکل پیدا شد (بالا با ✘){OFF}")
    sys.exit(1)
print(f"{GREEN}همه چیز سالم است.{OFF}")
print("اگر باز هم در گروه کار نکرد، این را بفرست:")
print("  grep -E 'NAME FILTER|AD NAME' logs/*.log | tail -40")
sys.exit(0)
