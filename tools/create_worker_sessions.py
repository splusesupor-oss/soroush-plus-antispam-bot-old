#!/usr/bin/env python3
"""Create ONE independent worker session safely.

Stop the bot first, then run one role at a time:
  python3 tools/create_worker_sessions.py management
  python3 tools/create_worker_sessions.py background

Each command needs one verification code for the same Soroush account.  The
primary session is never read, copied, or overwritten.
"""
from __future__ import annotations
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ROLES = {
    "management": "SOROUSH_MANAGEMENT_SESSION_STRING",
    "background": "SOROUSH_BACKGROUND_SESSION_STRING",
}


def load_env() -> None:
    try:
        rows = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for row in rows:
        if not row.strip() or row.lstrip().startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def save_env(key: str, value: str) -> None:
    rows = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    prefix = key + "="
    found = False
    output = []
    for row in rows:
        if row.startswith(prefix):
            output.append(prefix + value)
            found = True
        else:
            output.append(row)
    if not found:
        output.append(prefix + value)
    fd, temporary = tempfile.mkstemp(prefix=".env.worker.", dir=str(ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(output) + "\n")
        os.replace(temporary, ENV_FILE)
        try: ENV_FILE.chmod(0o600)
        except OSError: pass
    except BaseException:
        try: os.unlink(temporary)
        except OSError: pass
        raise


async def main(role: str) -> None:
    load_env()
    try:
        from splusthon import SoroushClient
        from splusthon.sessions import StringSession
    except ImportError as error:
        raise SystemExit("این ابزار را با python3 همان محیط ربات اجرا کنید.") from error

    api_id, api_hash = os.getenv("API_ID"), os.getenv("API_HASH")
    session = StringSession()
    client = SoroushClient(session, int(api_id), api_hash) if api_id and api_hash else SoroushClient(session)
    try:
        print(f"ساخت session مستقل {role}. session اصلی تغییر نمی‌کند.")
        await client.connect()
        authorized = await client.is_user_authorized()
        if not authorized:
            phone = input("شماره تلفن اکانت را با +98 وارد کنید: ").strip()
            await client.send_code_request(phone)
            code = input("کد تأیید سروش: ").strip()
            try:
                await client.sign_in(phone, code)
            except Exception as error:
                if "password" not in type(error).__name__.lower():
                    raise
                password = input("رمز دومرحله‌ای: ")
                await client.sign_in(password=password)
        value = client.session.save()
        if not value:
            raise RuntimeError("session string خالی است")
        save_env(ROLES[role], value)
        print(f"✅ session {role} ذخیره شد. آن را در چت یا ترمینال چاپ نکنید.")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    role = sys.argv[1].strip().lower() if len(sys.argv) == 2 else ""
    if role not in ROLES:
        raise SystemExit("استفاده: python3 tools/create_worker_sessions.py management|background")
    asyncio.run(main(role))
