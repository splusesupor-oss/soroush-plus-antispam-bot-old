"""تستِ ساختِ تماسِ گروهی (conference) و حذفِ کاملِ مسیرِ قدیمی.

تأیید می‌کند که:
  1. ``create_group_call`` فقط از ``conference.CreateConferenceCallRequest``
     استفاده می‌کند (نه از مسیرِ قدیمیِ ساختِ تماسِ تلگرام).
  2. version ارسال‌شده دقیقاً همانی است که فراخوان تعیین می‌کند (از config).
  3. لینکِ واقعیِ meet از ``ConferenceCreated.slug`` ساخته می‌شود:
     https://splus.ir/meet/{slug}
  4. اگر سرویس خطا بدهد، خطا برگردانده می‌شود و لینک/خطا به‌صورت tuple بازگشت داده
     می‌شود.
  5. در هیچ ماژولِ اجراییِ پروژه هیچ ارجاعی به مسیرِ قدیمی (ساختِ تماس یا
     دریافتِ لینکِ دعوت) باقی نمانده است.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modules.admin_tools as at

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class FakeCreated:
    """شبیه‌ساز پاسخِ واقعیِ conference.ConferenceCreated (دارای slug)."""

    def __init__(self, slug):
        self.slug = slug


class FakeError(Exception):
    pass


class FakeClient:
    """کلاینتی که درخواست را ثبت می‌کند و پاسخِ مشخص را برمی‌گرداند."""

    def __init__(self, result, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    async def __call__(self, request):
        self.calls.append(request)
        if self.exc is not None:
            raise self.exc
        return self.result


def run(coro):
    return asyncio.run(coro)


def _req_class_name():
    from splusthon.tl import functions
    return functions.conference.CreateConferenceCallRequest.__name__


def test_uses_conference_request_with_explicit_version():
    fc = FakeClient(FakeCreated("slug-abc-123"))
    link, error, created_at = run(
        at.create_group_call(fc, 123, title="تماس", version="X.Y"))
    req = fc.calls[0] if fc.calls else None

    check("فراخوانی شده (حداقل یک درخواست)",
          req is not None, "هیچ درخواستی فرستاده نشد")
    if req is not None:
        check("درخواست از نوع conference.CreateConferenceCallRequest است",
              req.__class__.__name__ == "CreateConferenceCallRequest"
              and req.__class__.__module__.endswith(".conference"),
              f"class={req.__class__}")
        check("version ارسال‌شده = X.Y", getattr(req, "version", None) == "X.Y",
              f"version={getattr(req, 'version', None)!r}")
        check("name ارسال‌شده = تماس", getattr(req, "name", None) == "تماس",
              f"name={getattr(req, 'name', None)!r}")
    check("لینک واقعی meet از slug",
          link == "https://splus.ir/meet/slug-abc-123", f"link={link!r}")
    check("بدون خطا", error is None, f"error={error!r}")


def test_default_version_from_constant():
    fc = FakeClient(FakeCreated("s"))
    link, error, _ = run(at.create_group_call(fc, 1, title="t"))
    req = fc.calls[0]
    check("پیش‌فرض version برابر DEFAULT_CONFERENCE_VERSION است",
          getattr(req, "version", None) == at.DEFAULT_CONFERENCE_VERSION,
          f"v={getattr(req, 'version', None)!r} default={at.DEFAULT_CONFERENCE_VERSION!r}")
    check("لینک ساخته شد", bool(link) and link.startswith("https://splus.ir/meet/"),
          f"link={link!r}")


def test_empty_slug_reports_error():
    fc = FakeClient(FakeCreated(""))
    link, error, _ = run(at.create_group_call(fc, 1, title="t"))
    check("وقتی slug خالی است لینک نباشد", link is None)
    check("پیام خطای فارسی برگردانده شود",
          error is not None and "سروش‌پلاس" in error, f"error={error!r}")


def test_rpc_error_returned_not_raised():
    fc = FakeClient(None, exc=FakeError("boom"))
    link, error, _ = run(at.create_group_call(fc, 1, title="t"))
    check("در صورت خطای RPC لینک نباشد", link is None)
    check("خطای واقعی در پیام باشد",
          error is not None and "boom" in error, f"error={error!r}")


def test_config_version_flow_in_handler_uses_real_request():
    """مسیرِ کامل: config → create_group_call → درخواستِ conference."""
    from modules.config_manager import ConfigManager
    import tempfile, json

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      encoding="utf-8")
    cfg_path = tmp.name
    json.dump({"conference_version": "42"}, tmp)
    tmp.close()

    cm = ConfigManager(cfg_path)
    version = cm.get("conference_version", at.DEFAULT_CONFERENCE_VERSION)

    fc = FakeClient(FakeCreated("cfg-slug"))
    link, error, _ = run(at.create_group_call(fc, 1, title="t", version=version))
    req = fc.calls[0]
    check("version از config خوانده شد (=42)",
          getattr(req, "version", None) == "42",
          f"v={getattr(req, 'version', None)!r}")
    check("لینک از slug ساخته شد", link == "https://splus.ir/meet/cfg-slug",
          f"link={link!r}")
    from pathlib import Path as _P
    _P(cfg_path).unlink(missing_ok=True)


def test_old_group_call_path_fully_removed():
    """در هیچ ماژولِ اجراییِ پروژه ارجاعی به مسیرِ قدیمی نمانده است."""
    old_symbols = ("CreateGroupCallRequest", "ExportGroupCallInviteRequest")
    offenders = []
    for root in ("modules", "handlers", "core", "economy"):
        base = ROOT / root
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            text = py.read_text(encoding="utf-8", errors="ignore")
            for sym in old_symbols:
                if sym in text:
                    offenders.append(f"{py.relative_to(ROOT)}:{sym}")
    check("مسیرِ قدیمی به‌طور کامل حذف شده",
          not offenders,
          "موارد باقی‌مانده: " + ", ".join(offenders))

    # و مطمئن شویم APIِ جدید هنوز استفاده می‌شود.
    ad = (ROOT / "modules" / "admin_tools.py").read_text(encoding="utf-8")
    check("API جدید (conference.CreateConferenceCallRequest) موجود است",
          "CreateConferenceCallRequest" in ad)


def _main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        print(f"\n{t}")
        t()
    print(f"\n=== conference_call: PASSED={PASSED} FAILED={FAILED} ===")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
