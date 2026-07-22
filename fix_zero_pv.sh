python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text()

if "پیوی فقط دستور صفر کردن تخلف" in s:
    print("already exists")
    exit()

insert = r'''
            # پیوی فقط دستور صفر کردن تخلف
            if event.is_private and "صفر" in clean_text:
                try:
                    parts = clean_text.split()
                    if len(parts) < 2:
                        await event.reply("❌ آیدی کاربر را بفرست")
                        return

                    username = parts[1].replace("@","")

                    user = await self.client.get_entity(username)
                    user_id = user.id

                    groups = load_active_groups()

                    done = False
                    for gid in groups:
                        count = self.tracker.get_count(int(gid), user_id)
                        if count:
                            self.tracker.reset_count(int(gid), user_id)
                            done = True
                            try:
                                await self.client.send_message(
                                    int(gid),
                                    f"✅ تخلفات @{username} صفر شد"
                                )
                            except:
                                pass

                    if done:
                        await event.reply("✅ تخلفات کاربر صفر شد")
                    else:
                        await event.reply("❌ این کاربر هیچ تخلف ثبت شده‌ای ندارد")

                except Exception as e:
                    await event.reply(f"❌ خطای صفر کردن از پیوی: {e}")

                return

'''

pos=s.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی")

if pos == -1:
    pos=s.find("if clean_text in [\"فعال سازی\", \"غیر فعال\"]")

if pos == -1:
    print("insert point not found")
else:
    s=s[:pos]+insert+s[pos:]
    p.write_text(s)
    print("zero pv fixed")
PY

python3 -m py_compile main.py && echo "syntax ok"
