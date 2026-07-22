"""
دریافت Session String برای سروش پلاس
اجرا: python get_session.py
بعد از دریافت، آن را در .env ذخیره کنید
"""
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from splusthon import SoroushClient
    from splusthon.sessions import StringSession
except ImportError:
    print("❌ splusthon نصب نیست")
    print("pip install splusthon")
    exit(1)

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

if api_id and api_hash:
    client = SoroushClient(StringSession(), int(api_id), api_hash)
else:
    # SPlusthon کلید پیش‌فرض دارد
    client = SoroushClient(StringSession())

async def main():
    print("🚀 اتصال به سروش پلاس...")
    await client.start()
    me = await client.get_me()
    print(f"✅ وارد شدید: {me.first_name} (ID: {me.id})")
    
    session_string = client.session.save()
    print("\n" + "="*60)
    print("🔑 SESSION STRING شما:")
    print("="*60)
    print(session_string)
    print("="*60)
    print("\nاین رشته را در فایل .env ذخیره کنید:")
    print(f"SOROUSH_SESSION_STRING={session_string}")
    
    # ذخیره خودکار
    with open(".env", "a", encoding="utf-8") as f:
        f.write(f"\nSOROUSH_SESSION_STRING={session_string}\n")
    print("\n✅ به صورت خودکار در .env ذخیره شد")

    await client.disconnect()

import asyncio
asyncio.run(main())
