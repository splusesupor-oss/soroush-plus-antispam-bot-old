from pathlib import Path

p = Path("test_main.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines):
    if line.strip() == "if is_spam:":
        indent = line[:len(line)-len(line.lstrip())]

        block = [
            indent + "# FINAL ADMIN GUARD",
            indent + "try:",
            indent + "    if is_admin(chat_id, username):",
            indent + "        print(f'FINAL ADMIN BYPASS: {username}')",
            indent + "        is_spam = False",
            indent + "        reason = ''",
            indent + "except Exception as e:",
            indent + "    print('FINAL ADMIN CHECK ERROR:', e)",
            ""
        ]

        lines[i:i] = block
        p.write_text("\n".join(lines)+"\n", encoding="utf-8")
        print("✅ محافظ نهایی ادمین اضافه شد خط", i+1)
        break
else:
    print("❌ if is_spam پیدا نشد")
