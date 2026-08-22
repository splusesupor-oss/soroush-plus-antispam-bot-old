#!/usr/bin/env python3
"""Create two independent SPlusthon StringSessions for one Soroush account.

Run on the Termux device that can receive the account's verification code:
    python tools/create_worker_sessions.py

It never changes SOROUSH_SESSION_STRING.  It creates and stores only:
    SOROUSH_MANAGEMENT_SESSION_STRING
    SOROUSH_BACKGROUND_SESSION_STRING
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
load_dotenv(ENV_FILE)

try:
    from splusthon import SoroushClient
    from splusthon.sessions import StringSession
except ImportError as error:
    raise SystemExit("splusthon نصب نیست: pip install splusthon") from error


def _save_env_value(key: str, value: str) -> None:
    """Replace one .env entry atomically without printing the secret."""
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    prefix = f"{key}="
    replaced = False
    output = []
    for line in lines:
        if line.startswith(prefix):
            output.append(prefix + value)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(prefix + value)
    fd, temporary = tempfile.mkstemp(prefix=".env.sessions.", dir=str(ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(output) + "\n")
        os.replace(temporary, ENV_FILE)
        try:
            ENV_FILE.chmod(0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _new_client():
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session = StringSession()  # Always creates a new auth session.
    if api_id and api_hash:
        return SoroushClient(session, int(api_id), api_hash)
    return SoroushClient(session)


async def _create(label: str, key: str) -> None:
    print(f"\nساخت session مستقل «{label}»")
    print("کد تأیید همان اکانت را فقط در همین ترمینال وارد کنید.")
    client = _new_client()
    try:
        await client.start()
        me = await client.get_me()
        session_string = client.session.save()
        if not session_string:
            raise RuntimeError("session string خالی است")
        _save_env_value(key, session_string)
        print(f"✅ session «{label}» برای حساب {getattr(me, 'id', '?')} ذخیره شد.")
    finally:
        await client.disconnect()


async def main() -> None:
    if not (os.getenv("SOROUSH_SESSION_STRING") or os.getenv("SESSION_STRING")):
        raise SystemExit("ابتدا session اصلی را در .env نگه دارید؛ حذفش نکنید.")
    print("session اصلی دست‌نخورده می‌ماند.")
    await _create("مدیریت", "SOROUSH_MANAGEMENT_SESSION_STRING")
    await _create("پس‌زمینه", "SOROUSH_BACKGROUND_SESSION_STRING")
    print("\n✅ هر دو session جدا ذخیره شدند. هیچ‌کدام را در ترمینال یا چت منتشر نکنید.")
    print("حالا برای فعال‌سازی معماری سه‌کلاینت، به ربات برگردید.")


if __name__ == "__main__":
    asyncio.run(main())
