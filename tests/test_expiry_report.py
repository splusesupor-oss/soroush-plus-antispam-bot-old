from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import group_expiry, group_storage
from modules.expiry_report import build_group_list, build_report


def _use_files(monkeypatch, tmp_path):
    groups_file = tmp_path / "groups.json"
    expiry_file = tmp_path / "group_expiry.json"
    monkeypatch.setattr(group_storage, "FILE", groups_file)
    monkeypatch.setattr(group_expiry, "FILE", expiry_file)
    group_storage._cache = group_storage._cache_mtime = None
    group_expiry._cache = group_expiry._cache_mtime = None
    return groups_file


def test_report_uses_current_group_and_expiry_storage(monkeypatch, tmp_path):
    groups_file = _use_files(monkeypatch, tmp_path)
    groups_file.write_text(json.dumps({
        "11": {"title": "گروه فعال", "active": True},
        "12": {"title": "گروه تمام", "active": False},
        "13": {"title": "بدون مهلت", "active": True},
    }, ensure_ascii=False), encoding="utf-8")
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    group_expiry.set_expiry(11, group_expiry.FIVE_DAYS, now=now - timedelta(days=3, hours=18))
    group_expiry.set_expiry(12, group_expiry.ONE_WEEK, now=now - timedelta(days=8))

    report = build_report(now=now)
    assert "گروه فعال" in report
    assert "۱ روز و ۶ ساعت" in report
    assert "❌ گروه: گروه تمام" in report
    assert "منقضی شده" in report
    assert "بدون مهلت" in report
    assert "تاریخ انقضا ثبت نشده" in report


def test_group_list_is_compact_and_uses_existing_storage(monkeypatch, tmp_path):
    groups_file = _use_files(monkeypatch, tmp_path)
    groups_file.write_text(json.dumps({
        "31": {"title": "گروه اول"},
        "32": {"title": "بدون تاریخ"},
    }, ensure_ascii=False), encoding="utf-8")
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    group_expiry.set_expiry(31, group_expiry.FIVE_DAYS, now=now - timedelta(days=4, hours=21))

    report = build_group_list(now=now)
    assert "1. گروه اول" in report
    assert "۳ ساعت باقی مانده" in report
    assert "بدون تاریخ" not in report
    assert "شناسه" not in report


def test_report_survives_invalid_expiry_data(monkeypatch, tmp_path):
    groups_file = _use_files(monkeypatch, tmp_path)
    groups_file.write_text(json.dumps({"44": {"title": "گروه خراب"}}, ensure_ascii=False), encoding="utf-8")
    group_expiry.FILE.write_text(json.dumps({"44": {"expires_at": "not-a-date"}}, ensure_ascii=False), encoding="utf-8")
    group_expiry._cache = group_expiry._cache_mtime = None

    report = build_report(now=datetime.now(timezone.utc))
    assert "گروه خراب" in report
    assert "تاریخ انقضا نامعتبر است" in report
