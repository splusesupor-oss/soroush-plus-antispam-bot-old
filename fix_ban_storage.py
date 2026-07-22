from pathlib import Path

p = Path("modules/admin_actions.py")
text = p.read_text(encoding="utf-8")

old = '''                username = getattr(user, "username", None)

                if username:
                    add_banned(chat_id, username)
                else:
                    add_banned(chat_id, str(user_id))'''

new = '''                username = getattr(user, "username", None)

                # ذخیره همیشه با ID
                add_banned(chat_id, str(user_id))

                # اگر username داشت ذخیره کن
                if username:
                    add_banned(chat_id, username)'''

if old in text:
    text = text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ ban storage fixed")
else:
    print("❌ block not found")
