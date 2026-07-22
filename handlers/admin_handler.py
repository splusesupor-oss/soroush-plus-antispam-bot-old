from modules.group_banned_words_control import enable, disable
async def handle_admin_commands(bot, event, text: str, admin_id: int, chat_id: int):


    """دستورات مدیریتی داخل گروه"""
    text = text.strip()

    if text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
        if not await bot.is_admin_user(event, admin_id):
            await event.respond("❌ فقط مدیر می‌تواند این دستور را اجرا کند")
            return

        if text == "لغو کلمات ممنوعه":
            disable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")
            return

        if text == "فعال کلمات ممنوعه":
            enable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")
            return

    if not text.startswith(("!", "/", ".")):
        return

    cmd_text = text[1:].strip()
    parts = cmd_text.split()

    if not parts:
        return

    cmd = parts[0].lower()

    if text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
        if not await bot.is_admin_user(event, admin_id):
            await event.respond("❌ فقط مدیر می‌تواند این دستور را اجرا کند")
            return
        if text == "لغو کلمات ممنوعه":
            print("DEBUG BANNED DISABLE:", chat_id)
            disable(chat_id)
            print("DEBUG AFTER DISABLE DONE")
            await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")
            return
        if text == "فعال کلمات ممنوعه":
            enable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")
            return

    try:
        if cmd in ["addword", "addban", "افزودن"]:
            if len(parts) < 2:
                await event.respond("❌ استفاده: !addword کلمه")
                return

            word = " ".join(parts[1:])

            if bot.config_manager.add_banned_word(word):
                await event.respond(f"✅ کلمه '{word}' اضافه شد.")
            else:
                await event.respond("⚠️ این کلمه قبلا وجود دارد.")

        elif cmd in ["remword", "removeword", "حذف"]:
            if len(parts) < 2:
                await event.respond("❌ استفاده: !remword کلمه")
                return

            word = " ".join(parts[1:])

            if bot.config_manager.remove_banned_word(word):
                await event.respond(f"✅ کلمه '{word}' حذف شد.")
            else:
                await event.respond("⚠️ کلمه پیدا نشد.")

        elif cmd in ["stats", "آمار"]:
            counts = bot.tracker.get_all_counts(chat_id)
            await event.respond(
                f"📊 تعداد کاربران متخلف: {len(counts)}"
            )

        elif cmd in ["reset", "ریست"]:
            if len(parts) >= 2 and parts[1].isdigit():
                bot.tracker.reset_count(chat_id, int(parts[1]))
                await event.respond("✅ شمارنده کاربر صفر شد.")
            else:
                bot.tracker.reset_group(chat_id)
                await event.respond("✅ شمارنده گروه صفر شد.")

        elif cmd in ["lock", "قفل"]:
            if bot.group_actions:
                await bot.group_actions.lock_group(chat_id)
                await event.respond("🔒 گروه قفل شد")

        elif cmd in ["unlock", "باز"]:
            if bot.group_actions:
                await bot.group_actions.unlock_group(chat_id)
                await event.respond("🔓 گروه باز شد")

        elif cmd in ["timelock", "قفل_ساعتی"]:
            if len(parts) >= 2 and parts[1].isdigit():
                if bot.group_actions:
                    await bot.group_actions.lock_group(
                        chat_id,
                        int(parts[1]) * 60
                    )
                    await event.respond("⏰ قفل ساعتی فعال شد")

        elif cmd in ["photo", "عکس"]:
            try:
                if len(parts) < 2:
                    await event.respond("❌ مسیر عکس را بده")
                    return

                await bot.group_actions.change_photo(
                    chat_id,
                    " ".join(parts[1:])
                )

                await event.respond("🖼️ عکس گروه تغییر کرد ✅")

            except Exception as e:
                await event.respond(f"❌ خطا در تغییر عکس: {e}")

        elif cmd in ["title", "اسم"]:
            if len(parts) >= 2:
                name = " ".join(parts[1:])
                if bot.group_actions:
                    await bot.group_actions.change_title(chat_id, name)
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
        bot.logger.log_error(f"خطا در دستور ادمین: {e}")
        import traceback
        traceback.print_exc()

