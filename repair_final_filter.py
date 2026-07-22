from pathlib import Path

p = Path("test_main.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# بررسی کلمات فیلتر شده گروه" in l:
        start = i
    if start and "if is_spam:" in l:
        end = i
        break

if start is None or end is None:
    print("❌ بخش پیدا نشد")
    exit()

new = r'''
            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = ""

            try:
                from modules.group_words_storage import get_words
                group_words = get_words(chat_id)

                for word in group_words:
                    if word and word in message_text:
                        group_word_spam = True
                        group_word_reason = f"فیلتر گروه ({word})"
                        break

            except Exception as e:
                self.logger.log_error(f"خطای کلمات گروه: {e}")

            # ادمین بدون فیلتر
            admin_bypass = False

            try:
                admin_bypass = is_admin(chat_id, username)
            except Exception:
                admin_bypass = False

            if admin_bypass:
                print(f"ADMIN BYPASS FILTER: {user_id}")
                is_spam = False
                reason = ""

            elif group_word_spam:
                is_spam = True
                reason = group_word_reason

            else:
                clean = message_text.strip()

                if len(clean) <= 3 or all(not c.isalnum() for c in clean):
                    is_spam = False
                    reason = ""
                else:
                    is_spam, reason = self.detector.is_spam(
                        message_text,
                        chat_id
                    )

'''

lines[start:end] = new.splitlines()

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ فیلتر و ادمین از نو ساخته شد")
