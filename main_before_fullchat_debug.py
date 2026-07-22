from modules.admin_storage import is_admin, add_admin, remove_admin
from modules.group_stats import add_message, add_deleted, add_kick, add_mute, make_report
from modules import ConfigManager, SpamDetector, BotLogger, UserTracker, AdminActions
from modules.jorat_haghighat import get_jorat, get_haghighat
from modules.font_converter import make_fonts
from modules.banned_storage import add_banned, remove_banned
from modules.group_words_commands import handle_group_word_command
from modules.group_storage import activate_group, deactivate_group, is_active
from modules.group_actions import GroupActions
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
from splusthon.tl.types import MessageEntityBold, MessageEntityBlockquote

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


from splusthon import types
from splusthon.tl import functions
# ---------------------------------------------------


class SoroushAntiSpamBot:
    def __init__(self, config_path="config/config.json"):
        print("🚀 در حال بارگذاری تنظیمات...")
        self.config_manager = ConfigManager(config_path=config_path)
        self.bot_sent_messages = []
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
        self.group_actions = None
        self.delete_notice_lock = set()
        self.punished_users = set()
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

        self.group_actions = GroupActions(
            self.client, self.logger)
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
                "شب بخیر": "🌙 شب تو هم بخیر، شاد و سلامت باشی",
                "عشقم": "❤️ قربونت، خوشحالم که اینجایی",
                "چطوری": "😊 خوبم، ممنون که پرسیدی",
                "رل بزنیم": "😄 من یه رباتم، ولی همیشه برای کمک اینجام",
                "خیلی دوست دارم": "❤️ محبتت قشنگه، ممنونم",
                "دوست دارم": "😊 ممنون از لطفت",
                "دوست دخترم میشی": "🤖 من فقط یه رباتم، ولی می‌تونم دوست خوبت باشم",
                "چیکار میکنی": "🤖 دارم پیام‌ها رو بررسی می‌کنم و به گروه کمک می‌کنم",

                "شب بخیر": "شب شما هم بخیر 🌙",
                "مرسی": "خواهش می‌کنم 🌹",
                "ممنون": "قابلی نداشت 😊"
            }

            jokes = ["بیوم چک","بیومچک",
                "😂 یکی به دوستش گفت چرا همیشه دیر میای؟ گفت چون عجله دارم، آروم آروم میام!",
                "🤣 رفتم باشگاه ثبت نام کنم گفتن هدفت چیه؟ گفتم فقط می‌خوام وقتی از پله بالا میرم با پله‌ها دوست باشم!",
                "😂 معلم گفت چرا مشقت سفیده؟ گفت چون با مداد سفید نوشتم که معلوم نباشه!",
                "🤣 یکی گفت گوشی جدید گرفتم خیلی باهوشه! پرسیدن چطور؟ گفت خودش می‌فهمه کی شارژ نداره!",
                "😂 بابام گفت چرا انقدر با گوشیت حرف می‌زنی؟ گفتم دارم با رفیقم چت می‌کنم. گفت پس چرا جواب نمیده؟ گفتم چون رفته شارژر بیاره!",
                "🤣 دکتر گفت باید کمتر شیرینی بخوری. گفتم چشم دکتر، از فردا کمتر می‌خورم... ولی تعداد دفعاتش همونه!",
                "😂 یکی پرسید چرا کتاب نمی‌خونی؟ گفت چون کتاب‌ها حرف نمی‌زنن، من با آدم‌ها راحت‌ترم!",
                "🤣 به دوستم گفتم چرا ساعت زنگ‌دارتو خاموش کردی؟ گفت چون هر روز صبح باهام دعوا می‌کنه!"]

            clean_text = message_text.strip()

            # ثبت آمار پیام گروه
            try:
                if not event.is_private:
                    sender_stats = await event.get_sender()
                    chat_stats = await event.get_chat()

                    add_message(
                        getattr(chat_stats, "id", 0),
                        getattr(sender_stats, "id", 0),
                        getattr(sender_stats, "username", "") or ""
                    )

            except Exception as e:
                self.logger.log_error(
                    f"خطای ثبت آمار پیام: {e}"
                )

            # اتصال دستورات فیلتر کلمات گروه
            try:
                sender = await event.get_sender()
                user_id = getattr(sender, "id", 0)

                chat = await event.get_chat()
                chat_id = getattr(chat, "id", 0)

                if await self.check_group_word_commands(
                    event,
                    clean_text,
                    chat_id,
                    user_id
                ):
                    return

            except Exception as e:
                self.logger.log_error(
                    f"خطای فیلتر گروه: {e}"
                )

            # بازی جرعت حقیقت
            clean_text = message_text.strip()

            if clean_text in ["جرعت", "جرات", "جرئت"]:
                await event.reply("🎯 جرعت:\n" + get_jorat())
                return

            if clean_text in ["حقیقت", "حقیقت بگو"]:
                await event.reply("🧠 حقیقت:\n" + get_haghighat())
                return



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

            for key, reply in auto_replies.items():
                if key in clean_text:
                    await event.reply(reply)
                    return


            # پاسخ معرفی ربات
            if clean_text.strip() in ["ربات", "روباه"]:
                await event.reply(
                    "🦊 سلام، من روباه هستم 🤖\n\n"
                    "برای آشنایی با امکانات و خدمات بیشتر، کلمه «راهنما» را ارسال کنید."
                )
                return

            # آمار گروه
            if clean_text in ["آمار گپ", "آمار گروه"]:
                member_count = 0

                try:
                    members = await self.client.get_participants(chat_id)
                    member_count = len(members)
                    print("MEMBERS OK:", member_count)
                    try:
                        chat = await self.client.get_entity(chat_id)
                        print("CHAT TYPE:", type(chat))
                        print("CHAT INFO:", chat)
                        print("CHAT ATTRS:", dir(chat))
                    except Exception as e:
                        print("CHAT DEBUG ERROR:", repr(e))

                except Exception as e:
                    print("MEMBERS ERROR:", repr(e))

                await event.reply(make_report(chat_id, member_count))
                return

            # راهنمای ربات
            if clean_text.strip() in ["راهنما", "/help", "!help", "help"]:
                help_text = (
                    "📌 راهنمای روباه\n\n"

                    "👤 کاربران:\n\n"

                    "💬 پاسخ‌های ساده:\n"
                    "سلام\n"
                    "خوبی\n"
                    "چخبر\n"
                    "چخبرا\n"
                    "مرسی\n"
                    "ممنون\n"
                    "شب بخیر\n"








                    "😂 جک:\n"
                    "فقط ارسال کنید:\n"
                    "جک\n\n"

                    "🎯 بازی جرعت حقیقت:\n"
                    "جرعت → یک جرعت تصادفی دریافت کنید\n"
                    "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\n\n"

                    "✍️ ساخت فونت:\n"
                    "فونت متن شما\n\n"

                    "🛡️ امنیت گروه:\n"
                    "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\n\n"

                    "👑 دستورات ادمین‌ها:\n\n"
"🔤 فیلتر کلمات گروه:\n"
"/فیلتر کلمه  ← افزودن کلمه ممنوعه\n"
"/رفع کلمه  ← حذف کلمه از فیلتر\n"
"/فیلترها  ← نمایش لیست فیلترهای گروه\n\n"
"✏️ تغییر اسم گروه:\n"
"!اسم نام جدید گروه\n\n"

                      "🗑️ حذف پیام:\n"
                      "حذف یک پیام با ریپلای:\n"
                      "پاک\n\n"
                      "حذف چند پیام آخر گروه:\n"
                      "پاک 10\n"
                      "پاک 50\n"
                      "پاک 100\n\n"

                    "🔇 سکوت کاربر:\n"
                    "روی پیام ریپلای کنید و بنویسید:\n"
                    "سکوت\n\n"
                    "🔊 رفع سکوت کاربر:\n"
                    "روی پیام ریپلای کنید و بنویسید:\n"
                    "رفع سکوت\n\n"

                    "🚪 اخراج کاربر:\n"
                    "روی پیام ریپلای کنید و بنویسید:\n"
                    "اخراج\n\n"

                    "♻️ آزاد کردن کاربر:\n"
                    "برای آزاد کردن کاربر محروم شده بنویسید:\n"
                    "آزاد\n\n"

                    "⚠️ صفر کردن تخلفات:\n"
                    "با سازنده ربات تماس بگیرید:\n"
                    "@osine1"
                )

                entities = []

                def u16(x):
                    return len(x.encode("utf-16-le")) // 2

                for word in [
                    "💬 پاسخ‌های ساده:",
                    "😂 جک:",
                    "🎯 بازی جرعت حقیقت:",
                    "✍️ ساخت فونت:",
                    "🛡️ امنیت گروه:",
                    "👑 دستورات ادمین‌ها:",
                    "🗑️ حذف پیام:"
                      "حذف یک پیام با ریپلای:",
                      "حذف چند پیام آخر گروه:",
                    "🔇 سکوت کاربر:",
                    "🔊 رفع سکوت کاربر:",
                    "🚪 اخراج کاربر:",
                    "♻️ آزاد کردن کاربر:"
                ]:
                    pos = help_text.find(word)
                    if pos != -1:
                        entities.append(
                            MessageEntityBold(
                                offset=u16(help_text[:pos]),
                                length=u16(word)
                            )
                        )

                for word in ["پاک\n\n", "سکوت", "رفع سکوت", "اخراج", "آزاد"]:
                    pos = help_text.rfind(word)
                    if pos != -1:
                        entities.append(
                            MessageEntityBlockquote(
                                offset=u16(help_text[:pos]),
                                length=u16(word)
                            )
                        )

                await event.reply(
                    help_text,
                    formatting_entities=entities
                )
                return

            # فعال و غیرفعال کردن گروه توسط مالک اصلی
            if clean_text in ["فعال سازی", "غیر فعال"]:
                try:
                    sender = await event.get_sender()
                    print("OWNER DEBUG:", getattr(sender, "username", None), getattr(sender, "id", None), getattr(sender, "first_name", None))
                    owner = getattr(sender, "username", None)

                    if owner != "osine1":
                        await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                        return

                    chat = await event.get_chat()
                    gid = getattr(chat, "id", None)
                    title = getattr(chat, "title", )

                    if clean_text == "فعال سازی":
                        activate_group(gid, title)
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"
                        )

                    else:
                        deactivate_group(gid, title)
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                        )

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return

            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_id = getattr(chat, "id", None)

            # اجرای دستورات مدیریتی
            if clean_text.startswith(("!", "/", ".")):
                try:
                    sender = await event.get_sender()
                    await self.handle_admin_commands(
                        event,
                        clean_text,
                        getattr(sender, "id", 0),
                        chat_id
                    )
                    return
                except Exception as e:
                    self.logger.log_error(f"خطای اجرای دستور مدیر: {e}")
            chat_title = getattr(chat, "title", "Unknown")

            user_id = getattr(sender, "id", None)
            username = (
                getattr(sender, "username", None)
                or getattr(sender, "first_name", "Unknown")
            )

            # ثبت ادمین توسط مالک ربات
            if clean_text == "ثبت گروه":
                try:
                    owner = getattr(sender, "username", "")

                    if owner != "osine1":
                        await event.reply(
                            "❌ فقط مالک ربات اجازه ثبت گروه دارد"
                        )
                        return

                    chat = await event.get_chat()

                    gid = getattr(chat, "id", None)
                    title = getattr(chat, "title", )

                    activate_group(
                        gid,
                        title
                    )

                    await event.reply(
                        f"✅ گروه «{title}» ثبت شد\\n"
                        f"🆔 {gid}"
                    )

                except Exception as e:
                    await event.reply(
                        f"❌ خطا در ثبت گروه: {e}"
                    )

                return


            # فعال و غیرفعال کردن گروه توسط مالک اصلی
            if clean_text in ["فعال سازی", "غیر فعال"]:
                try:
                    sender = await event.get_sender()
                    print("OWNER DEBUG:", getattr(sender, "username", None), getattr(sender, "id", None), getattr(sender, "first_name", None))
                    owner = getattr(sender, "username", None)

                    if owner != "osine1":
                        await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                        return

                    chat = await event.get_chat()
                    gid = getattr(chat, "id", None)
                    title = getattr(chat, "title", )

                    if clean_text == "فعال سازی":
                        activate_group(gid, title)
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"
                        )

                    else:
                        deactivate_group(gid, title)
                        await event.reply(
                            f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                        )

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return

            chat = await event.get_chat()
            sender = await event.get_sender()



            # ثبت ادمین توسط مالک ربات

            if clean_text.startswith("ثبت ادمین"):
                try:
                    owner = getattr(sender, "username", "")
                    if owner != "osine1":
                        await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                        return

                    admin_username = None

                    if event.reply_to:
                        reply_msg = await self.client.get_messages(
                                chat_id,
                                ids=event.reply_to.reply_to_msg_id
                            )
                        if reply_msg:
                            user = await reply_msg.get_sender()
                            admin_username = getattr(user, "username", None)

                    if not admin_username:
                        parts = clean_text.split()
                        if len(parts) >= 3:
                            admin_username = parts[2].replace("@", "")

                    if not admin_username:
                        await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                        return

                    add_admin(chat_id, admin_username)
                    await event.reply(f"✅ ادمین @{admin_username} ثبت شد")

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return


            # برکناری ادمین توسط مالک ربات
            if clean_text.startswith("برکناری ادمین"):
                try:
                    owner = getattr(sender, "username", "")
                    if owner != "osine1":
                        await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                        return

                    admin_username = None

                    if event.reply_to:
                        reply_msg = await self.client.get_messages(
                            chat_id,
                            ids=event.reply_to.reply_to_msg_id
                        )

                        if reply_msg:
                            user = await reply_msg.get_sender()
                            admin_username = getattr(user, "username", None)

                    if not admin_username:
                        parts = clean_text.split()
                        if len(parts) >= 3:
                            admin_username = parts[2].replace("@", "")

                    if not admin_username:
                        await event.reply("❌ باید ریپلای کنید یا @username بدهید")
                        return

                    if remove_admin(chat_id, admin_username):
                        await event.reply(f"✅ دسترسی ادمین @{admin_username} حذف شد")
                    else:
                        await event.reply("❌ این کاربر ادمین نیست")

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return


            # حذف چند پیام آخر با پاک عدد
            if clean_text.startswith("پاک "):
                try:
                    sender_username = getattr(sender, "username", None)

                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه حذف پیام دارند")
                        return

                    parts = clean_text.split()

                    if len(parts) == 2 and parts[1].isdigit():
                        count = min(int(parts[1]), 500)

                        msgs = await self.client.get_messages(
                            chat_id,
                            limit=count
                        )

                        ids = [m.id for m in msgs if getattr(m, "id", None)]

                        if ids:
                            await self.client.delete_messages(
                                chat_id,
                                ids
                            )
                            try:
                                from modules.group_stats import add_deleted
                                for _ in ids:
                                    add_deleted(chat_id, user_id, username)
                            except Exception:
                                pass

                            try:
                                from modules.group_stats import add_deleted
                                add_deleted(chat_id, user_id, username)
                            except Exception:
                                pass

                            try:
                                add_deleted(chat_id, user_id, username)
                            except Exception:
                                pass

                        return

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")
                    return

            # حذف پیام با ریپلای
            if clean_text == "پاک":
                try:
                    sender_username = getattr(sender, "username", None)

                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه حذف پیام دارند")
                        return

                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام ریپلای کنید")
                        return

                    await self.client.delete_messages(
                        chat_id,
                        event.reply_to.reply_to_msg_id
                    )

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")

                return

# اخراج کاربر با ریپلای
            if clean_text == "اخراج":
                try:
                    sender = await event.get_sender()
                    sender_username = getattr(sender, "username", None)

                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه اخراج دارند")
                        return

                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    target_user = await reply_msg.get_sender()

                    if not target_user:
                        await event.reply("❌ کاربر پیدا نشد")
                        return

                    add_kick(chat_id)
                    await self.client.kick_participant(
                        chat_id,
                        target_user
                    )

                    await event.reply("✅ کاربر اخراج شد")

                except Exception as e:
                    self.logger.log_error(f"خطای اخراج: {e}")
                    await event.reply(f"❌ خطا در اخراج:\n{e}")

                return


# آزاد کردن کاربر محروم شده از لیست
            if clean_text == "آزاد":
                try:
                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    user = await reply_msg.get_sender()

                    if not user:
                        await event.reply("❌ کاربر پیدا نشد")
                        return

                    entity = await self.client.get_input_entity(chat_id)
                    user_entity = await self.client.get_input_entity(user)

                    await self.client(
                        functions.channels.EditBannedRequest(
                            channel=entity,
                            participant=user_entity,
                            banned_rights=types.ChatBannedRights(
                                until_date=None
                            )
                        )
                    )

                    username = getattr(user, "username", None)

                    if username:
                        remove_banned(chat_id, username)

                    await event.reply("♻️ کاربر آزاد شد")

                except Exception as e:
                    await event.reply(f"❌ خطا در آزاد کردن:\n{e}")

                return

# سکوت کاربر با ریپلای
            if clean_text == "سکوت":
                try:
                    sender = await event.get_sender()

                    sender_username = getattr(sender, "username", None)
                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه استفاده از سکوت را دارند")
                        return

                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    if not reply_msg:
                        await event.reply("❌ پیام ریپلای شده پیدا نشد")
                        return

                    target_user = await reply_msg.get_sender()

                    if not target_user:
                        await event.reply("❌ کاربر پیدا نشد")
                        return

                    # بررسی ادمین بودن (سازگار با SPlus)
                    try:
                        admins = await self.client.get_participants(chat_id)
                        admin_ids = [
                            getattr(x, "id", 0)
                            for x in admins
                            if getattr(x, "admin_rights", None)
                        ]

                        if target_user.id in admin_ids:
                            await event.reply("⚠️ این کاربر ادمین است و سکوت نشد")
                            return
                    except Exception:
                        pass

                    add_mute(chat_id)
                    result = await self.admin_actions.mute_user(
                        chat_id,
                        target_user.id,
                        0
                    )

                    if result:
                        await event.reply(
                            f"🔇 کاربر {getattr(target_user,'username','کاربر')} سکوت شد"
                        )
                    else:
                        await event.reply("❌ انجام سکوت ناموفق بود")

                except Exception as e:
                    self.logger.log_error(
                        f"خطای سکوت کاربر: {e}"
                    )
                    await event.reply(f"❌ خطا در سکوت کاربر:\n{e}")

                return



            # رفع سکوت کاربر با ریپلای
            if clean_text == "رفع سکوت":
                try:
                    if not event.reply_to:
                        await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                        return

                    reply_msg = await self.client.get_messages(
                        chat_id,
                        ids=event.reply_to.reply_to_msg_id
                    )

                    if not reply_msg:
                        await event.reply("❌ پیام پیدا نشد")
                        return

                    target_user = await reply_msg.get_sender()

                    result = await self.admin_actions.unmute_user(
                        chat_id,
                        target_user.id
                    )

                    if result:
                        await event.reply("🔊 سکوت کاربر برداشته شد")
                    else:
                        await event.reply("❌ رفع سکوت انجام نشد")

                except Exception as e:
                    self.logger.log_error(f"خطای رفع سکوت: {e}")
                    await event.reply(f"❌ خطا در رفع سکوت:\n{e}")

                return

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


            # ضد اسپم پیام‌های پشت سرهم
            try:
                import time

                if not hasattr(self, "flood_messages"):
                    self.flood_messages = {}

                if chat_id not in self.flood_messages:
                    self.flood_messages[chat_id] = []

                self.flood_messages[chat_id].append(
                    (time.time(), event.message.id)
                )

                now = time.time()

                self.flood_messages[chat_id] = [
                    x for x in self.flood_messages[chat_id]
                    if now - x[0] <= 10
                ]

                if len(self.flood_messages[chat_id]) >= 5:
                    ids = [
                        x[1]
                        for x in self.flood_messages[chat_id]
                    ]

                    await self.client.delete_messages(
                        chat_id,
                        ids
                    )

                    self.flood_messages[chat_id] = []

                    if chat_id not in self.delete_notice_lock:
                        self.delete_notice_lock.add(chat_id)
                        await event.reply(
                            "⚠️ ارسال پیام‌های زیاد پشت سرهم حذف شد"
                        )

                    return

            except Exception as e:
                self.logger.log_error(
                    f"خطای ضد فلود: {e}"
                )

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

            # استثنا: پیام‌های فوروارد شده از @osine1 هیچ‌وقت حذف نشوند
            try:
                if getattr(event.message, "fwd_from", None):
                    forward_sender = getattr(event.message.fwd_from, "from_id", None)

                    if forward_sender:
                        sender_entity = await self.client.get_entity(forward_sender)

                        if getattr(sender_entity, "username", "") == "osine1":
                            print("✅ فوروارد @osine1 محافظت شد")
                            return
            except Exception as e:
                print("خطای بررسی فوروارد:", e)

            # استثنا: فورواردهای کانال @osine1 حذف نشوند
            try:
                if getattr(event.message, "fwd_from", None):
                    fwd = event.message.fwd_from
                    fwd_id = getattr(getattr(fwd, "from_id", None), "channel_id", None)

                    if fwd_id == 22389465:
                        print("✅ فوروارد کانال osine1 محافظت شد")
                        return
            except Exception as e:
                print("خطای تشخیص فوروارد:", e)

            # بررسی تکرار شدید داخل یک پیام
            try:
                import re

                words = re.findall(r"\\w+|[آ-ی]+", message_text.lower())
                repeat_found = False

                for w in set(words):
                    if len(w) >= 3 and words.count(w) >= 8:
                        repeat_found = True
                        break

                if repeat_found:
                    from modules.user_map import save_user

                    save_user(chat_id, username, user_id)

                    count = self.tracker.increment(chat_id, user_id)

                    await self.admin_actions.delete_message(chat_id, event=event)

                    await self.admin_actions.send_warning(
                        chat_id=chat_id,
                        username=username,
                        reason="تکرار بیش از حد داخل یک پیام",
                        count=count,
                        threshold=self.config_manager.get("spam_threshold", 3),
                        reply_to=None
                    )

                    if self.tracker.should_punish(chat_id, user_id):
                        punish_key = f"{chat_id}:{user_id}"

                        if punish_key not in self.punished_users:
                            self.punished_users.add(punish_key)

                            await self.admin_actions.punish_user(
                                chat_id,
                                user_id,
                                username
                            )

                    return

            except Exception as e:
                self.logger.log_error(f"خطای بررسی تکرار داخلی: {e}")

            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = None

            try:
                from modules.group_words_storage import get_words

                group_words = get_words(chat_id)

                for word in group_words:
                    if word and word in message_text:
                        group_word_spam = True
                        group_word_reason = f"کلمه ممنوعه ({word})"
                        break

            except Exception as e:
                self.logger.log_error(f"خطای بررسی کلمات گروه: {e}")

            # بررسی اسپم
            if group_word_spam:
                is_spam = True
                reason = group_word_reason
            else:
                is_spam, reason = self.detector.is_spam(message_text)

            if is_spam:
                # افزایش شمارنده
                from modules.user_map import save_user

                save_user(chat_id, username, user_id)

                count = self.tracker.increment(chat_id, user_id)

                threshold = self.config_manager.get("spam_threshold", 3)

                # لاگ
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

                # حذف پیام
                if self.config_manager.get("delete_spam", True):
                    await self.admin_actions.delete_message(chat_id, event=event)

                # هشدار فقط ۵ بار
                if count <= 5:
                    await self.admin_actions.send_warning(
                        chat_id=chat_id,
                        username=username,
                        reason=reason,
                        count=count,
                        threshold=threshold,
                        reply_to=None
                    )

                # بررسی مجازات
                if self.tracker.should_punish(chat_id, user_id):
                    punish_key = f"{chat_id}:{user_id}"

                    if punish_key not in self.punished_users:
                        self.punished_users.add(punish_key)

                        print(
                            f"⚠️ کاربر {username}({user_id}) به آستانه {threshold} رسید - اعمال مجازات"
                        )

                        await self.admin_actions.punish_user(chat_id, user_id, username)

                        # بعد از مجازات شمارنده تخلف صفر شود
                        self.tracker.reset_count(chat_id, user_id)
                        self.punished_users.discard(punish_key)
                # پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد
                pass

        except Exception as e:
            self.logger.log_error(f"خطا در هندل پیام: {e}")
            import traceback
            traceback.print_exc()


    async def check_group_word_commands(self, event, text, chat_id, user_id):
        try:
            print("FILTER ARGS:", repr(text), type(text), chat_id, user_id)
            return await handle_group_word_command(
                self,
                event,
                text,
                chat_id,
                user_id
            )
        except Exception as e:
            self.logger.log_error(f"خطای فیلتر کلمه: {e}")
            return False

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

            elif cmd in ["lock", "قفل"]:
                if self.group_actions:
                    await self.group_actions.lock_group(chat_id)
                    await event.respond("🔒 گروه قفل شد")

            elif cmd in ["unlock", "باز"]:
                if self.group_actions:
                    await self.group_actions.unlock_group(chat_id)
                    await event.respond("🔓 گروه باز شد")

            elif cmd in ["timelock", "قفل_ساعتی"]:
                if len(parts) >= 2 and parts[1].isdigit():
                    if self.group_actions:
                        await self.group_actions.lock_group(
                            chat_id,
                            int(parts[1]) * 60
                        )
                        await event.respond("⏰ قفل ساعتی فعال شد")

            elif cmd in ["photo", "عکس"]:
                try:
                    if len(parts) < 2:
                        await event.respond("❌ مسیر عکس را بده")
                        return

                    await self.group_actions.change_photo(
                        chat_id,
                        " ".join(parts[1:])
                    )

                    await event.respond("🖼️ عکس گروه تغییر کرد ✅")

                except Exception as e:
                    await event.respond(f"❌ خطا در تغییر عکس: {e}")

            elif cmd in ["title", "اسم"]:
                if len(parts) >= 2:
                    name = " ".join(parts[1:])
                    if self.group_actions:
                        await self.group_actions.change_title(chat_id, name)
                        await event.respond("✅ اسم گروه تغییر کرد")

            elif cmd in ["help", "راهنما"]:
                await event.respond(
                    "🤖 دستورات مدیر:\n"
                    "!addword\n"
                    "!remword\n"
                    "!stats\n"
                    "!reset\n"
                    "!قفل\n"
                    "!باز\n"
                    "!قفل_ساعتی دقیقه\n"
                    "!اسم نام جدید\n"
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


            # کنترل فعال بودن گروه
            if not event.is_private:
                chat_lock = await event.get_chat()
                lock_id = getattr(chat_lock, "id", None)

                sender_lock = await event.get_sender()
                owner_lock = getattr(sender_lock, "username", None)

                # مالک همیشه اجازه فعال/غیر فعال کردن دارد
                if text not in ["فعال سازی", "غیر فعال"] or owner_lock != "osine1":
                    if not is_active(lock_id):
                        return



              # پیوی فقط دستور صفر کردن تخلف
            if event.is_private:
                text = (event.message.message or "").strip()

                if "صفر" in text:
                    try:
                        import re
                        from modules.group_storage import load_groups

                        m = re.search(r"@([A-Za-z0-9_]+)", text)
                        if not m:
                            await event.reply("❌ آیدی کاربر پیدا نشد")
                            return

                        username = m.group(1)

                        groups = load_groups()
                        if not groups:
                            await event.reply("❌ هیچ گروهی ثبت نشده")
                            return

                        import json

                        with open("logs/user_map.json", "r", encoding="utf-8") as f:
                            user_map = json.load(f)

                        user_id = None

                        for gid, users in user_map.items():
                            if username.lower() in users:
                                user_id = int(users[username.lower()])
                                break

                        if not user_id:
                            await event.reply("❌ کاربر در لیست ثبت شده پیدا نشد")
                            return

                        reset_groups = []
                        all_counts = self.tracker.get_all_counts()

                        for gid, users in all_counts.items():
                            if str(user_id) in users:
                                self.tracker.reset_count(int(gid), user_id)
                                reset_groups.append(gid)

                                try:
                                    await self.client.send_message(
                                        int(gid),
                                        f"✅ تخلفات @{username} صفر شد"
                                    )
                                except Exception as send_err:
                                    self.logger.log_error(
                                        f"خطای ارسال پیام صفر کردن در گروه {gid}: {send_err}"
                                    )

                        if not reset_groups:
                            await event.reply("❌ این کاربر هیچ تخلف ثبت شده‌ای ندارد")
                            return

                        await event.reply("✅ انجام شد")

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
