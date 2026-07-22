from pathlib import Path

p = Path("test_main.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# بررسی کلمات فیلتر شده گروه" in l:
        start = i
    if start and l.strip() == "if is_spam:":
        end = i
        break

if start is None or end is None:
    print("❌ محدوده پیدا نشد")
    exit()

new = '''            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = None

            try:
                from modules.group_words_storage import get_words

                group_words = get_words(chat_id)

                for word in group_words:
                    if word and word in message_text:
                        group_word_spam = True
                        group_word_reason = f"فیلتر گروه ({word})"
                        break

            except Exception as e:
                self.logger.log_error(f"خطای بررسی کلمات گروه: {e}")


            # بررسی ادمین
            admin_bypass = False

            try:
                admin_bypass = is_admin(chat_id, username)
                if admin_bypass:
                    print(f"ADMIN BYPASS FINAL: {username}")

            except Exception as e:
                print("ADMIN CHECK ERROR:", e)
                admin_bypass = False


            if admin_bypass:
                is_spam = False
                reason = ""

            elif group_word_spam:
                is_spam = True
                reason = group_word_reason

            else:
                clean_check = message_text.strip()

                if len(clean_check) <= 3 or all(not ch.isalnum() for ch in clean_check):
                    is_spam = False
                    reason = ""

                else:
                    is_spam, reason = self.detector.is_spam(
                        message_text,
                        chat_id
                    )
'''

lines[start:end] = new.splitlines()

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ کل فیلتر + ادمین بازسازی شد")
