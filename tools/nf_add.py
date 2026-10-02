#!/usr/bin/env python3
"""➕ افزودن/حذف/نمایش فیلتر اسم مستقیماً از ترمینال.

برای جدا کردن دو چیز از هم:

* اگر اینجا اضافه شود و در گروه **کار کند** → مشکل از مسیر *دستور* است.
* اگر اینجا اضافه شود و باز هم کار **نکند** → مشکل از مسیر *اجرا* است.

ربات نیازی به ری‌استارت ندارد؛ فایل با mtime دوباره خوانده می‌شود.

    python tools/nf_add.py list
    python tools/nf_add.py add 24073694 حسین
    python tools/nf_add.py add 24073694 🍆
    python tools/nf_add.py del 24073694 حسین
    python tools/nf_add.py test 24073694 "حسین احمدی"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import name_filters as nf
from modules.group_id import normalize_group_id

USAGE = __doc__


def show_all():
    print(f"فایل: {nf.FILE}")
    if not Path(nf.FILE).exists():
        print("<<فایل وجود ندارد — هنوز هیچ فیلتری ثبت نشده>>")
        return
    data = nf._load()
    if not data:
        print("<<خالی>>")
        return
    for group_key, items in data.items():
        terms = ", ".join(str(i.get("term")) for i in items)
        print(f"  گروه {group_key}: {terms}")


def main():
    nf.reset_cache()
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0

    action = args[0]

    if action == "list":
        if len(args) == 1:
            show_all()
        else:
            key = normalize_group_id(args[1])
            print(f"گروه {key}: {nf.list_terms(args[1])}")
        return 0

    if action in {"add", "del", "test"} and len(args) < 3:
        print(USAGE)
        return 2

    chat_id = args[1]
    term = " ".join(args[2:])
    key = normalize_group_id(chat_id)

    if action == "add":
        ok, problem, display = nf.add(chat_id, term)
        if ok:
            print(f"✅ «{display}» به گروه {key} اضافه شد")
        else:
            print(f"❌ اضافه نشد: {problem}")
        nf.reset_cache()
        print(f"فیلترهای این گروه: {nf.list_terms(chat_id)}")
        print(f"فایل: {nf.FILE}")
        print("\nحالا بگذار همان کاربر یک پیام بفرستد، بعد:")
        print("  bash tools/nf_live.sh")
        return 0 if ok else 1

    if action == "del":
        ok, problem, display = nf.remove(chat_id, term)
        print(f"✅ «{display}» حذف شد" if ok else f"❌ حذف نشد: {problem}")
        nf.reset_cache()
        print(f"فیلترهای این گروه: {nf.list_terms(chat_id)}")
        return 0 if ok else 1

    if action == "test":
        class _User:
            id = 0
            first_name = term
            last_name = None
            username = None

        matched = nf.match_name(chat_id, _User)
        print(f"گروه {key} | نام «{term}»")
        print(f"  نرمال‌شده : {nf.normalize(term)!r}")
        print(f"  فیلترها   : {nf.list_terms(chat_id)}")
        print(f"  نتیجه     : {matched!r}")
        print("  ✅ می‌خورد" if matched else "  ❌ نمی‌خورد")
        return 0 if matched else 1

    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
