#!/usr/bin/env python3
"""Create a fresh primary Soroush session after AuthKeyUnregisteredError.

Stop run.sh first. This replaces only SOROUSH_SESSION_STRING in .env.
"""
from __future__ import annotations
import asyncio
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def load_env():
    try:
        rows = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for row in rows:
        if "=" not in row or row.lstrip().startswith("#"):
            continue
        key, value = row.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def save_primary(value: str):
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    key = "SOROUSH_SESSION_STRING="
    changed = False
    output = []
    for line in lines:
        if line.startswith(key):
            output.append(key + value)
            changed = True
        else:
            output.append(line)
    if not changed:
        output.append(key + value)
    fd, temporary = tempfile.mkstemp(prefix=".env.primary.", dir=str(ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(output) + "\n")
        os.replace(temporary, ENV_FILE)
        try:
            ENV_FILE.chmod(0o600)
        except OSError:
            pass
    except BaseException:
        try: os.unlink(temporary)
        except OSError: pass
        raise


load_env()
try:
    from splusthon import SoroushClient
    from splusthon.sessions import StringSession
except ImportError as error:
    raise SystemExit("با python3 اجرا کنید: python3 tools/renew_primary_session.py") from error


async def main():
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session = StringSession()
    client = SoroushClient(session, int(api_id), api_hash) if api_id and api_hash else SoroushClient(session)
    print("ورود تازه به session اصلی. کد تأیید را فقط در همین ترمینال وارد کنید.")
    try:
        await client.start()
        me = await client.get_me()
        value = client.session.save()
        if not value:
            raise RuntimeError("session string خالی است")
        save_primary(value)
        print(f"✅ session اصلی جدید برای حساب {getattr(me, 'id', '?')} ذخیره شد.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
