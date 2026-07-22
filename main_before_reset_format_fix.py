from modules import ConfigManager, SpamDetector, BotLogger, UserTracker, AdminActions
from modules.font_converter import make_fonts
import random
"""
ربات مدیریت گروه سروش پلاس - ضد هرزنامه
اجرا روی حساب کاربری شما با SPlusthon (فورک Telethon برای سروش)

ویژگی‌ها:
- بررسی تمام پیام‌های جدید گروه
- تشخیص لینک، شماره، آیدی، کلمات تبلیغاتی
- حذف خودکار + سایلنت/بن بعد از 3 تخلف
- وایت لیست مدیران
- افزودن کلمات ممنوعه از طریق فایل یا دستور
- لاگ کامل
- ماژولار

نویسنده: Agent for Soroush Plus
"""

import os
import asyncio
import sys
from dotenv import load_dotenv

# لود env
load_dotenv()

# اگر پوشه ماژول‌ها در مسیر نیست اضافه کن
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# تلاش برای import SPlusthon
try:
    from splusthon import SoroushClient, events
    from splusthon.sessions import StringSession
    SPLUSTHON_AVAILABLE = True
except ImportError:
    SPLUSTHON_AVAILABLE = False
    print("⚠️ کتابخانه splusthon نصب نیست. ابتدا pip install splusthon را اجرا کنید")
    print("راهنما: pip install -r requirements.txt")

# ---------------------------------------------------


class SoroushAntiSpamBot:
    def __init__(self, config_path="config/config.json"):
        print("🚀 در حال بارگذاری تنظیمات...")
        self.config_manager = ConfigManager(config_path=config_path)
        self.logger = BotLogger(
            log_file=self.config_manager.get(
                "log_file", "logs/deleted_messages.log"))
        self.detector = SpamDetector(self.config_manager)
        self.tracker = UserTracker(
            spam_counts_file=self.config_manager.get(
                "spam_counts_file",
                "logs/spam_counts.json"),
            threshold=self.config_manager.get(
                "spam_threshold",
                3))

        self.client = None
        self.admin_actions = None
        self.delete_notice_lock = set()
        self.repeat_messages = {}

        self.logger.log_info("✅ تنظیمات بارگذاری شد")
        self.logger.log_info(
            f"📚 تعداد کلمات ممنوعه: {len(self.config_manager.banned_words)}")
        self.logger.log_info(
            f"🛡️ تعداد کاربران سفید: {len(self.config_manager.whitelisted_ids)}")

    async def initialize_client(self):
        """ساخت کلاینت سروش"""
        if not SPLUSTHON_AVAILABLE:
            raise RuntimeError("SPlusthon نصب نیست")

        # اولویت: SESSION_STRING از env یا config
        session_str = os.getenv("SOROUSH_SESSION_STRING") or self.config_manager.get(
            "session_string", "")
        api_id = os.getenv("API_ID") or self.config_manager.get("api_id")
        api_hash = os.getenv("API_HASH") or self.config_manager.get("api_hash")

        # اگر session string وجود داشته باشد از آن استفاده کن
        if session_str:
            session = StringSession(session_str)
        else:
            session = StringSession()  # جدید می‌سازد و بعد باید ذخیره کنی

        # SPlusthon شامل api_id/hash پیش‌فرض برای سروش است، ولی اگر کاربر
        # مقادیر شخصی دارد استفاده می‌کنیم
        if api_id and api_hash:
            self.client = SoroushClient(session, api_id, api_hash)
        else:
            self.client = SoroushClient(session)

        self.admin_actions = AdminActions(
            self.client, self.logger, self.config_manager)
        return self.client

    async def handle_new_message(self, event):
        """هندلر اصلی برای پیام‌های جدید"""
        try:
            # اگر پیام متنی نیست رد کن (مثلا سرویس)
            if not event.message or not hasattr(event.message, 'message'):
                return

            # اطلاعات پیام
            message_text = getattr(event.message, "message", "") or ""
            # برای کپشن عکس/فایل هم چک کن
            if not message_text and hasattr(
                    event.message, 'file') and event.message.file:
                # اگر فایل دارد، نام فایل یا کپشن را چک کن
                try:
                    caption = getattr(event.message, 'caption', None) or ""
                    message_text = caption
                except BaseException:
                    pass

            if not message_text:
                return

            # پاسخ خودکار پیام‌ها
            auto_replies = {
                "سلام": "سلام خوبی؟",
                "درود": "درود بر شما 🌹",
                "خوبی": "ممنون، تو خوبی؟",
                "چطوری": "خوبم، مرسی 😊",
                "چه خبر": "سلامتی بچها 🦊",
                "چخبر": "سلامتی بچها 🦊",
                "چخبرا": "سلامتی بچها 🦊",
                "ربات": "سلام جانم؟",
                "صبح بخیر": "صبح شما هم بخیر ☀️",
                "شب بخیر": "شب شما هم بخیر 🌙",
                "مرسی": "خواهش می‌کنم 🌹",
                "ممنون": "قابلی نداشت 😊"
            }

            jokes = [
                "😂 یکی به دوستش گفت چرا همیشه دیر میای؟ گفت چون عجله دارم، آروم آروم میام!",
                "🤣 رفتم باشگاه ثبت نام کنم گفتن هدفت چیه؟ گفتم فقط می‌خوام وقتی از پله بالا میرم با پله‌ها دوست باشم!",
                "😂 معلم گفت چرا مشقت سفیده؟ گفت چون با مداد سفید نوشتم که معلوم نباشه!",
                "🤣 یکی گفت گوشی جدید گرفتم خیلی باهوشه! پرسیدن چطور؟ گفت خودش می‌فهمه کی شارژ نداره!",
                "😂 بابام گفت چرا انقدر با گوشیت حرف می‌زنی؟ گفتم دارم با رفیقم چت می‌کنم. گفت پس چرا جواب نمیده؟ گفتم چون رفته شارژر بیاره!",
                "🤣 دکتر گفت باید کمتر شیرینی بخوری. گفتم چشم دکتر، از فردا کمتر می‌خورم... ولی تعداد دفعاتش همونه!",
                "😂 یکی پرسید چرا کتاب نمی‌خونی؟ گفت چون کتاب‌ها حرف نمی‌زنن، من با آدم‌ها راحت‌ترم!",
                "🤣 به دوستم گفتم چرا ساعت زنگ‌دارتو خاموش کردی؟ گفت چون هر روز صبح باهام دعوا می‌کنه!"]

            clean_text = message_text.strip()

            # فونت ساز چند مدلی
            if clean_text.startswith("فونت "):
                font_text = clean_text.replace("فونت ", "", 1).strip()

                if font_text:
                    try:
                        result = make_fonts(font_text)

                        if isinstance(result, list):
                            result = "\n\n".join(result)

                        await event.reply(
                            "✨ فونت‌های ساخته شده:\n\n" + str(result)
                        )

                    except Exception as e:
                        self.logger.log_error(
                            f"خطای فونت ساز: {e}"
                        )

                return


            # فونت ساز گروه
            if clean_text == "جک":
                import random
                await event.reply(random.choice(jokes))
                return

            if clean_text in auto_replies:
                await event.reply(auto_replies[clean_text])
                return

            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_id = getattr(chat, "id", None)
            chat_title = getattr(chat, "title", "Unknown")

            user_id = getattr(sender, "id", None)
            username = (
                getattr(sender, "username", None)
                or getattr(sender, "first_name", "Unknown")
            )

            # حذف دستی پیام با ریپلای و کلمه پاک
            if clean_text == "پاک":
                try:
                    reply_id = getattr(
                        event.message,
                        "reply_to_msg_id",
                        None
                    )

                    if reply_id:
                        await self.client.delete_messages(
                            chat.id,
                            [reply_id]
                        )

                        try:
                            await event.delete()
                        except Exception:
                            pass

                        await event.reply(
                            "✅ با موفقیت پاک شد"
                        )

                    return

                except Exception as e:
                    self.logger.log_error(
                        f"DELETE COMMAND ERROR: {e}"
                    )
                    return


            # حذف پیام‌های تکراری بیشتر از ۳ بار
            try:
                key = f"{chat_id}:{message_text.strip()}"

                if key not in self.repeat_messages:
                    self.repeat_messages[key] = []

                self.repeat_messages[key].append(event.message.id)

                if len(self.repeat_messages[key]) > 3:
                    ids = self.repeat_messages[key]

                    await self.client.delete_messages(
                        chat_id,
                        ids
                    )

                    self.repeat_messages[key] = []

                    if chat_id not in self.delete_notice_lock:
                        self.delete_notice_lock.add(chat_id)
                        await event.reply(
                            "⚠️ پیام تکراری بیش از حد ارسال شد و پاک شد"
                        )

                    return

            except Exception as e:
                self.logger.log_error(
                    f"خطای حذف تکراری: {e}"
                )


            # حذف پیام های فوروارد شده
            try:
                if getattr(event.message, "fwd_from", None):
                    await self.client.delete_messages(
                        chat_id,
                        [event.message.id]
                    )

                    if chat_id not in self.delete_notice_lock:
                        self.delete_notice_lock.add(chat_id)
                        await event.reply(
                            "⚠️ پیام فوروارد شده حذف شد"
                        )

                    return

            except Exception as e:
                self.logger.log_error(
                    f"خطای حذف فوروارد: {e}"
                )

            # بررسی اسپم
            is_spam, reason = self.detector.is_spam(message_text)

            if is_spam:
                # افزایش شمارنده
                count = self.tracker.increment(chat_id, user_id)
                threshold = self.config_manager.get("spam_threshold", 3)

                # لاگ
                self.logger.log_deleted_message(
                    user_id=user_id,
                    username=username,
                    group_id=chat_id,
                    group_title=chat_title,
                    original_text=message_text,
                    reason=reason,
                    message_id=event.message.id
                )

                # حذف پیام اگر تنظیم شده
                if self.config_manager.get("delete_spam", True):
                    deleted = await self.admin_actions.delete_message(chat_id, event=event)
                    if deleted:
                        print(
                            f"🗑️ حذف شد | {chat_title} | {username} | دلیل: {reason} | تعداد تخلف: {count}")

                # ارسال هشدار
                await self.admin_actions.send_warning(
                    chat_id=chat_id,
                    username=username,
                    reason=reason,
                    count=count,
                    threshold=threshold,
                    reply_to=None  # برای جلوگیری از ریپلای به پیام حذف شده
                )

                # بررسی مجازات
                if self.tracker.should_punish(chat_id, user_id):
                    print(
                        f"⚠️ کاربر {username}({user_id}) به آستانه {threshold} رسید - اعمال مجازات")
                    await self.admin_actions.punish_user(chat_id, user_id, username)
            else:
                # پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد
                pass

        except Exception as e:
            self.logger.log_error(f"خطا در هندل پیام: {e}")
            import traceback
            traceback.print_exc()

    async def handle_admin_commands(self, event, text: str, admin_id: int, chat_id: int):
        """دستورات مدیریتی داخل گروه"""
        text = text.strip()

        if not text.startswith(("!", "/", ".")):
            return

        cmd_text = text[1:].strip()
        parts = cmd_text.split()

        if not parts:
            return

        cmd = parts[0].lower()

        try:
            if cmd in ["addword", "addban", "افزودن"]:
                if len(parts) < 2:
                    await event.respond("❌ استفاده: !addword کلمه")
                    return

                word = " ".join(parts[1:])

                if self.config_manager.add_banned_word(word):
                    await event.respond(f"✅ کلمه '{word}' اضافه شد.")
                else:
                    await event.respond("⚠️ این کلمه قبلا وجود دارد.")

            elif cmd in ["remword", "removeword", "حذف"]:
                if len(parts) < 2:
                    await event.respond("❌ استفاده: !remword کلمه")
                    return

                word = " ".join(parts[1:])

                if self.config_manager.remove_banned_word(word):
                    await event.respond(f"✅ کلمه '{word}' حذف شد.")
                else:
                    await event.respond("⚠️ کلمه پیدا نشد.")

            elif cmd in ["stats", "آمار"]:
                counts = self.tracker.get_all_counts(chat_id)
                await event.respond(
                    f"📊 تعداد کاربران متخلف: {len(counts)}"
                )

            elif cmd in ["reset", "ریست"]:
                if len(parts) >= 2 and parts[1].isdigit():
                    self.tracker.reset_count(chat_id, int(parts[1]))
                    await event.respond("✅ شمارنده کاربر صفر شد.")
                else:
                    self.tracker.reset_group(chat_id)
                    await event.respond("✅ شمارنده گروه صفر شد.")

            elif cmd in ["help", "راهنما"]:
                await event.respond(
                    "🤖 دستورات مدیر:\n"
                    "!addword\n"
                    "!remword\n"
                    "!stats\n"
                    "!reset\n"
                    "!help"
                )

        except Exception as e:
            self.logger.log_error(f"خطا در دستور ادمین: {e}")
            import traceback
            traceback.print_exc()

    async def is_admin_user(self, event, user_id):
        try:
            sender = await event.get_sender()
            return self.config_manager.is_admin(user_id)
        except Exception as e:
            self.logger.log_error(f"خطا در تشخیص مدیر: {e}")
            return False

    async def run(self):
        """اجرای ربات"""
        await self.initialize_client()

        await self.client.connect()

        @self.client.on(events.NewMessage())
        async def new_message_handler(event):

            print("📩 پیام دریافت شد:", getattr(event.message, "message", ""))

            if event.out:
                return

            text = (event.message.message or "").strip()

            # پیوی فقط دستور صفر کردن تخلف
            if event.is_private:
                text = (event.message.message or "").strip()

                if text.startswith("صفر "):
                    try:
                        parts = text.split()

                        if len(parts) >= 3:
                            username = parts[1].replace("@", "")
                            group_link = parts[2]

                            group = await self.client.get_entity(group_link)
                            user = await self.client.get_entity(username)

                            self.tracker.reset_count(
                                group.id,
                                user.id
                            )

                            await self.client.send_message(
                                group.id,
                                f"✅ تخلفات @{username} توسط مدیریت صفر شد"
                            )

                    except Exception as e:
                        self.logger.log_error(
                            f"خطای صفر کردن از پیوی: {e}"
                        )

                return

            await self.handle_new_message(event)


        print("✅ ربات فعال شد و منتظر پیام است")

        await self.client.run_until_disconnected()


async def main():
    bot = SoroushAntiSpamBot()
    await bot.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
