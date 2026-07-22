async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            name = (
                getattr(user, "username", None)
                or getattr(user, "first_name", None)
                or str(getattr(user, "id", ""))
            )

            participant = getattr(user, "participant", None)

            if participant:
                kind = type(participant).__name__.lower()

                if "creator" in kind:
                    owner = name
                elif "admin" in kind:
                    admins.append(name)

    except Exception as e:
        return f"خطا: {e}"

    msg = f"مالک گروه: {owner}\n\nادمین های گروه:\n"

    if admins:
        for i, a in enumerate(admins, 1):
            msg += f"{i}- {a}\n"
    else:
        msg += "ندارد\n"

    return msg

async def handle_new_message(self, event):
        """هندلر اصلی برای پیام‌های جدید"""
        try:
            # اگر پیام متنی نیست رد کن (مثلا سرویس)
            if not event.message or not hasattr(event.message, 'message'):
                return

            # اطلاعات پیام
            message_text = event.message.message or event.message.text or ""
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

            # حذف دستی پیام با ریپلای و کلمه پاک
            if clean_text == "پاک":
                try:
                    sender = await event.get_sender()
                except Exception as e:
                    print("DELETE COMMAND ERROR:", e)
                    return

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

            # پیوی فقط دستورات ادمین
            if event.is_private:
                sender = await event.get_sender()


async def main():
    bot = SoroushAntiSpamBot()
    await bot.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

