from pathlib import Path
import tokenize

p = Path("handlers/message_handler.py")

data = p.read_text(encoding="utf-8")

# تبدیل همه tab ها به 4 فاصله
data = data.expandtabs(4)

lines = data.splitlines()

# پیدا کردن خطوط خراب تاریخچه
start = None
end = None

for i,l in enumerate(lines):
    if "ذخیره تاریخچه" in l:
        start=i
    if start is not None and "# بررسی اسپم" in l:
        end=i
        break

if start is None or end is None:
    print("history marker not found")
    exit()

# سطح درست: همان سطح group_word_spam
indent="          "

block=f"""
{indent}# ذخیره تاریخچه پیام برای تشخیص تکرار
{indent}try:
{indent}    add_message(chat_id, user_id, event.message.id, message_text)
{indent}except Exception as e:
{indent}    print("history save error:", e)

{indent}# بررسی تاریخچه پیام‌های تکراری
{indent}try:
{indent}    if is_repeat(chat_id, user_id, message_text):
{indent}        print("🚨 HISTORY REPEAT BAN:", username, user_id)
{indent}        ids = get_message_ids(chat_id, user_id)

{indent}        if ids:
{indent}            await bot.client.delete_messages(chat_id, ids)

{indent}        await bot.admin_actions.ban_user(chat_id, user_id)
{indent}        clear_user(chat_id, user_id)
{indent}        return

{indent}except Exception as e:
{indent}    print("history repeat error:", e)

""".strip("\n")

lines[start:end]=block.splitlines()

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("done")
