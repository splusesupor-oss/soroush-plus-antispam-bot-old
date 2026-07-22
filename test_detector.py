"""
تست ماژول تشخیص اسپم بدون نیاز به اتصال به سروش
"""
from modules import ConfigManager, SpamDetector

config = ConfigManager(config_path="config/config.json")
detector = SpamDetector(config)

test_messages = [
    "سلام دوستان چطورید؟",
    "خرید فالوور ارزان فقط 10 هزار تومان",
    "به کانال ما جوین شوید t.me/mychannel",
    "شماره من 09121234567 تماس بگیرید",
    "آیدی من @myid پیام بدید",
    "www.example.com کلیک کنید",
    "این یک پیام کاملا عادی است",
    "تخفیف ویژه فقط امروز!!! برای خرید به پی وی مراجعه کنید",
    "@everyone لطفا به همه اطلاع دهید",
    "0912 123 4567",
    "سایت شرط بندی با جایزه ویژه http://bet.com",
    "سلام آیدی من @test123",
    "عضو کانال ما شوید @channel",
]

print("="*70)
print("🧪 تست تشخیص هرزنامه")
print("="*70)

for msg in test_messages:
    is_spam, reason = detector.is_spam(msg)
    status = "🚫 اسپم" if is_spam else "✅ سالم"
    print(f"{status} | {msg[:50]:<50} | دلیل: {reason}")

print("\n" + "="*70)
print(f"📚 تعداد کلمات ممنوعه بارگذاری شده: {len(config.banned_words)}")
print(f"🛡️ لیست سفید: {config.whitelisted_ids}")
print("="*70)
