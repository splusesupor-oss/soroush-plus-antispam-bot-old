from modules.riddles import check_answer
from modules.group_stats import add_message

async def handle_new_message(bot, event):
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

        jokes = [
"رفتم دکتر گفتم حافظه‌ام ضعیف شده، گفت از کی؟ گفتم چی از کی؟ 😂",
"معلم گفت چرا دیر اومدی؟ گفتم خواب دیدم دارم فوتبال بازی می‌کنم، وقت اضافه خوردیم 😂",
"به دوستم گفتم چرا گوشی‌تو خاموش کردی؟ گفت شارژ نداشتم روشنش کنم 😂",
"یکی گفت چرا همیشه لبخند می‌زنی؟ گفتم چون قبض‌ها رو باز نمی‌کنم 😂",
"رفیقم گفت رژیم گرفتم، پرسیدم چی می‌خوری؟ گفت فقط غذاهای سبک مثل پیتزا 😂",
"گفتم اینترنت قطع شده، گفتن وصلش کن. گفتم اگه وصل بود که پیام نمی‌دادم 😂",
"یکی رفت خواستگاری گفتن شغلت چیه؟ گفت متخصص خوابیدن روی مبل 😂",
"به کامپیوتر گفتم خسته‌ای؟ گفت نه فقط هنگ کردم 😂",
"بابام گفت چرا دیر خوابیدی؟ گفتم خوابم نمی‌برد، گفت خب بیدار نباش 😂",
"دوستم گفت چرا کتاب نمی‌خونی؟ گفتم آخرش رو بلدم، همه می‌میرن 😂",
"گوشی جدید گرفتم، هنوز خودش منو نمی‌شناسه 😂",
"یکی گفت پول داری؟ گفتم آره، توی خاطراتم 😂",
"رفتم باشگاه ثبت نام کنم، گفتن هدفت چیه؟ گفتم رسیدن به یخچال بدون نفس نفس زدن 😂",
"معلم پرسید آینده‌ات رو چطور می‌بینی؟ گفتم با چشمام 😂",
"یکی گفت چرا عینک زدی؟ گفتم چون چشمام بدون کمک نمی‌بینه 😂",
"گفتم چرا ساعتت کار نمی‌کنه؟ گفت وقت ندارم درستش کنم 😂",
"دوستم گفت ماشینم خیلی باهوشه، گفتم چرا؟ گفت خودش می‌فهمه کی بنزین نداره 😂",
"یکی پرسید چرا انقدر ساکتی؟ گفتم دارم به حرفای خودم گوش میدم 😂",
"مامانم گفت اتاقتو مرتب کن، گفتم چشم، ولی چشمام شلوغه 😂",
"گفتم خوابم میاد، گفت بخواب، گفتم اینترنت ندارم دانلودش کنم 😂",
"یکی گفت چقدر خوش شانسی، گفتم آره فقط شانسم خبر نداره 😂",
"رفتم بانک گفتن رمزت چیه؟ گفتم یادم نیست، گفتن پس پولت هم یادش نیست 😂",
"دوستم گفت ورزش می‌کنم، گفتم چه ورزشی؟ گفت بالا پایین کردن کنترل تلویزیون 😂",
"گفتم چرا دیر کردی؟ گفت دیر نکردم، زود نیومدم 😂",
"یکی گفت زندگی سخته، گفتم آره مخصوصا وقتی شارژ گوشی ۱ درصده 😂",
"گفتم چرا لپ‌تاپت کند شده؟ گفت مثل صاحبش پیر شده 😂",
"یکی گفت چرا همیشه آنلاین هستی؟ گفتم چون آفلاین بودن بلد نیستم 😂",
"معلم گفت چرا مشقت ناقصه؟ گفت بقیه‌ش رو فردا می‌نویسم، هنوز فردا نشده 😂",
"رفتم خرید، فروشنده گفت چیزی می‌خوای؟ گفتم نه فقط قیمت‌ها رو نگاه می‌کنم و گریه می‌کنم 😂",
"یکی گفت چای می‌خوری؟ گفتم نه، ولی چای منو می‌خوره 😂",
"گوشی زنگ خورد، جواب دادم، خودش بود 😂",
"گفتم چرا تلویزیون نگاه نمی‌کنی؟ گفت حوصله ندارم ببینم چی حوصله ندارم 😂",
"یکی گفت خیلی باهوشی، گفتم خودم هم تازه فهمیدم 😂",
"رفیقم گفت خواب دیدم پولدار شدم، گفتم بیدار شدی؟ گفت آره فقیرتر شدم 😂",
"گفتم چرا در یخچال رو باز کردی؟ گفت ببینم چیزی تغییر کرده یا نه 😂",
"یکی گفت کار سختیه، گفتم آره مخصوصا وقتی انجامش ندی 😂",
"پدرم گفت چرا گوشی دستته؟ گفتم دارم دنبال گوشی می‌گردم 😂",
"یکی گفت چرا دیر جواب دادی؟ گفتم داشتم جواب مناسب پیدا می‌کردم، پیدا نشد 😂",
"گفتم امروز چه روزیه؟ گفت همون روزیه که دیروز منتظرش بودی 😂",
"یکی گفت آینده‌ات روشنه، گفتم فقط قبض برقش زیاده 😂"
]

        chat_id = event.chat_id
        sender = await event.get_sender()
        user_id = sender.id if sender else 0

        clean_text = message_text.strip()
        # RIDDLE_SAFE_INSERTED
        if clean_text == "چیستان":
            try:
                q = new_riddle(chat_id, user_id)
                await event.reply("🧩 چیستان:\n\n" + q + "\n\n⏳ ۵۰ ثانیه فرصت داری جواب بده")

                async def riddle_timer():
                    import asyncio
                    await asyncio.sleep(50)
                    answer = get_answer(chat_id, user_id)
                    if answer:
                        await event.reply(f"⏰ زمان چیستان تمام شد!\n✅ پاسخ: {answer}")

                asyncio.create_task(riddle_timer())

            except Exception as e:
                bot.logger.log_error(f"خطای چیستان: {e}")
            return


        # بررسی جواب چیستان
        try:
            if check_answer(chat_id, user_id, clean_text):
                await event.reply("🎉 آفرین! پاسخ درست بود ✅")
                return
        except Exception as e:
            bot.logger.log_error(f"خطای بررسی جواب چیستان: {e}")

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
            bot.logger.log_error(
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
            bot.logger.log_error(
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
                    bot.logger.log_error(
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
                try:
                    await event.reply(reply)
                except Exception as e:
                    bot.logger.log_error(f"خطای ارسال پاسخ {event.chat_id}: {e}")
                return


        # پاسخ معرفی ربات
        if clean_text.strip() in ["ربات", "روباه"]:
            await event.reply(
                "🦊 سلام، من روباه هستم 🤖\n\n"
                "برای آشنایی با امکانات و خدمات بیشتر، کلمه «راهنما» را ارسال کنید."
            )
            return


        if clean_text == "ریست آمار":
            try:
                from modules.group_stats import load_stats, save_stats

                data = load_stats()
                gid = str(chat_id)

                if gid in data:
                    old_members = data[gid].get("members", 0)

                    data[gid]["messages"] = 0
                    data[gid]["deleted"] = 0
                    data[gid]["kicked"] = 0
                    data[gid]["muted"] = 0
                    data[gid]["users"] = {}
                    data[gid]["members"] = old_members

                    save_stats(data)

                await event.reply("✅ آمار گروه ریست شد\n👥 تعداد اعضا حفظ شد")
            except Exception as e:
                await event.reply(f"❌ خطا: {e}")

            return

        # آمار گروه
        if clean_text in ["آمار گپ", "آمار گروه"]:
            member_count = 0

            try:
                global functions

                from splusthon.tl import functions
                entity = await bot.client.get_input_entity(chat_id)
                full = await bot.client(
                    functions.channels.GetFullChannelRequest(entity)
                )
                member_count = full.full_chat.participants_count
            except Exception as e:
                print("MEMBER COUNT ERROR:", repr(e))
                member_count = 0

            print("FINAL MEMBER COUNT:", member_count)
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
                "🧩 چیستان\n"
                "یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن\n\n"

                "✍️ ساخت فونت:\n"
                "فونت متن شما\n\n"

                "🛡️ امنیت گروه:\n"
                "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\n\n"

                "👑 دستورات ادمین‌ها:\n\n"
"**🔤 فیلتر کلمات گروه:**\n"
                  "/فیلتر کلمه  ← افزودن کلمه ممنوعه\n"
                  "/رفع کلمه  ← حذف کلمه از فیلتر\n"
                  "/فیلترها  ← نمایش لیست فیلترهای گروه\n\n"
                  "📊 **آمار گروه**\n"
                  "نمایش آمار پیام‌ها، اعضا و کاربران فعال گروه\n\n"
                  "♻️ **ریست آمار**\n"
                  "صفر کردن آمار گروه (به جز تعداد اعضا)\n\n"
                  "**✏️ تغییر اسم گروه:**\n"
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

            # بولد کردن عنوان چیستان
            try:
                idx = help_text.find("🧩 چیستان")
                if idx >= 0:
                    entities.append(
                        MessageEntityBold(
                            offset=u16(idx),
                            length=u16(len("🧩 چیستان"))
                        )
                    )
            except Exception:
                pass

            for word in [
                    "🧩 چیستان",
                  "🧩 چیستان:",
                    "💬 پاسخ‌های ساده:",
                  "😂 جک:",
                  "🎯 بازی جرعت حقیقت:",
                  "✍️ ساخت فونت:",
                  "🛡️ امنیت گروه:",
                  "👑 دستورات ادمین‌ها:",
                  "🔤 فیلتر کلمات گروه:",
                  "📊 **آمار گروه**",
                  "♻️ **ریست آمار**",
                  "**✏️ تغییر اسم گروه:**",
                  "🗑️ حذف پیام:",
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
        if clean_text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
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
                bot.logger.log_error(f"خطای اجرای دستور کلمات ممنوعه: {e}")

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
                bot.logger.log_error(f"خطای اجرای دستور مدیر: {e}")
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
                    reply_msg = await bot.client.get_messages(
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
                    reply_msg = await bot.client.get_messages(
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

                    msgs = await bot.client.get_messages(
                        chat_id,
                        limit=count
                    )

                    ids = [m.id for m in msgs if getattr(m, "id", None)]

                    if ids:
                        await bot.client.delete_messages(
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

                await bot.client.delete_messages(
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

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                target_user = await reply_msg.get_sender()

                if not target_user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                add_kick(chat_id)
                await bot.client.edit_permissions(
                    chat_id,
                    target_user,
                    until_date=None,
                    view_messages=False
                )

                await event.reply("✅ کاربر اخراج شد")

            except Exception as e:
                bot.logger.log_error(f"خطای اخراج: {e}")
                await event.reply(f"❌ خطا در اخراج:\n{e}")

            return


# آزاد کردن کاربر محروم شده از لیست
        if clean_text == "آزاد":
            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                entity = await bot.client.get_input_entity(chat_id)
                user_entity = await bot.client.get_input_entity(user)

                await bot.client(
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

                reply_msg = await bot.client.get_messages(
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
                    admins = await bot.client.get_participants(chat_id)
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

                result = await bot.admin_actions.mute_user(
                    chat_id,
                    target_user.id
                )

                if result:
                    add_mute(chat_id)
                    await event.reply(
                        f"🔇 کاربر {getattr(target_user,'username','کاربر')} سکوت شد"
                    )
                else:
                    await event.reply("❌ انجام سکوت ناموفق بود")

            except Exception as e:
                bot.logger.log_error(
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

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                if not reply_msg:
                    await event.reply("❌ پیام پیدا نشد")
                    return

                target_user = await reply_msg.get_sender()

                result = await bot.admin_actions.unmute_user(
                    chat_id,
                    target_user.id
                )

                if result:
                    add_mute(chat_id)
                    await event.reply("🔊 سکوت کاربر برداشته شد")
                else:
                    await event.reply("❌ رفع سکوت انجام نشد")

            except Exception as e:
                bot.logger.log_error(f"خطای رفع سکوت: {e}")
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
                    await bot.client.delete_messages(
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
                bot.logger.log_error(
                    f"DELETE COMMAND ERROR: {e}"
                )
                return


        # ضد اسپم پیام‌های پشت سرهم
        try:
            import time

            if not hasattr(self, "flood_messages"):
                bot.flood_messages = {}

            if chat_id not in bot.flood_messages:
                bot.flood_messages[chat_id] = []

            bot.flood_messages[chat_id].append(
                (
                    time.time(),
                    event.message.id,
                    user_id,
                    message_text.strip()
                )
            )

            now = time.time()

            bot.flood_messages[chat_id] = [
                x for x in bot.flood_messages[chat_id]
                if now - x[0] <= 10
            ]

            user_msgs = [
                x for x in bot.flood_messages[chat_id]
                if x[2] == user_id
            ]

            # فقط پیام‌های تکراری یک کاربر حذف شوند
            if len(user_msgs) >= 5:

                texts = [
                    x[3]
                    for x in user_msgs
                ]

                normalized = [
                    t.replace(" ", "")
                     .replace("\n", "")
                    for t in texts
                ]

                # پیام‌های متفاوت مکالمه عادی هستند
                if len(set(normalized)) > 2:
                    return

                ids = [
                    x[1]
                    for x in user_msgs
                ]

                await bot.client.delete_messages(
                    chat_id,
                    ids
                )

                bot.flood_messages[chat_id] = []

                if chat_id not in bot.delete_notice_lock:
                    bot.delete_notice_lock.add(chat_id)
                    await event.reply(
                        "⚠️ ارسال پیام تکراری پشت سرهم حذف شد"
                    )

                return

        except Exception as e:
            bot.logger.log_error(
                f"خطای ضد فلود: {e}"
            )

        except Exception as e:
            bot.logger.log_error(
                f"خطای حذف تکراری: {e}"
            )


        # حذف پیام های فوروارد شده
        try:
            if getattr(event.message, "fwd_from", None):
                await bot.client.delete_messages(
                    chat_id,
                    [event.message.id]
                )

                if chat_id not in bot.delete_notice_lock:
                    bot.delete_notice_lock.add(chat_id)
                    await event.reply(
                        "⚠️ پیام فوروارد شده حذف شد"
                    )

                return

        except Exception as e:
            bot.logger.log_error(
                f"خطای حذف فوروارد: {e}"
            )

        # استثنا: پیام‌های فوروارد شده از @osine1 هیچ‌وقت حذف نشوند
        try:
            if getattr(event.message, "fwd_from", None):
                forward_sender = getattr(event.message.fwd_from, "from_id", None)

                if forward_sender:
                    sender_entity = await bot.client.get_entity(forward_sender)

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

                await bot.admin_actions.delete_message(
                    chat_id,
                    event=event
                )

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    await bot.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                return

        except Exception as e:
            bot.logger.log_error(f"خطای بررسی تکرار داخلی: {e}")

        # بررسی کلمات فیلتر شده گروه
        group_word_spam = False
        group_word_reason = None

        # دستورات مدیریت کلمات نباید توسط فیلتر گرفته شوند
        word_admin_commands = (
            "فیلتر کلمه",
            "حذف کلمه",
            "افزودن کلمه",
            "ثبت کلمه",
            "لیست کلمات",
            "پاک کردن کلمات"
        )

        if any(message_text.startswith(x) for x in word_admin_commands):
            group_word_spam = False

        try:
            from modules.group_words_storage import get_words

            group_words = get_words(chat_id)

            for word in group_words:
                if word and word in message_text:
                    group_word_spam = True
                    group_word_reason = f"فیلتر گروه ({word})"
                    break

        except Exception as e:
            bot.logger.log_error(f"خطای بررسی کلمات گروه: {e}")

        # بررسی اسپم
        if group_word_spam:
            is_spam = True
            reason = group_word_reason
        else:
            is_spam, reason = bot.detector.is_spam(message_text, chat_id)

        if is_spam:
            # افزایش شمارنده
            from modules.user_map import save_user

            save_user(chat_id, username, user_id)

            count = bot.tracker.increment(chat_id, user_id)

            threshold = bot.config_manager.get("spam_threshold", 3)

            # لاگ
            # لاگ
            bot.logger.log_deleted_message(
                user_id=user_id,
                username=username,
                group_id=chat_id,
                group_title=chat_title,
                original_text=message_text,
                reason=reason,
                message_id=event.message.id
            )

            # حذف پیام
            if bot.config_manager.get("delete_spam", True):
                await bot.admin_actions.delete_message(chat_id, event=event)

            # هشدار فقط ۵ بار
            if count <= 5:
                await bot.admin_actions.send_warning(
                    chat_id=chat_id,
                    username=username,
                    reason=reason,
                    count=count,
                    threshold=threshold,
                    reply_to=None
                )

            # بررسی مجازات
            if bot.tracker.should_punish(chat_id, user_id):
                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    print(
                        f"⚠️ کاربر {username}({user_id}) به آستانه {threshold} رسید - اعمال مجازات"
                    )

                    await bot.admin_actions.punish_user(chat_id, user_id, username)

                    # بعد از مجازات شمارنده تخلف صفر شود
                    bot.tracker.reset_count(chat_id, user_id)
                    bot.punished_users.discard(punish_key)
            # پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد
            pass

    except Exception as e:
        bot.logger.log_error(f"خطا در هندل پیام: {e}")
        import traceback
        traceback.print_exc()


