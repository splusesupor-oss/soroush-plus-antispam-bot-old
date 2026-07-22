python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text()

start=s.find("            # پیوی فقط دستور صفر کردن تخلف")
if start!=-1:
    end=s.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی", start)
    s=s[:start]+s[end:]

block=r'''
            # صفر کردن تخلفات از پیوی مالک
            if clean_text.startswith("صفر"):
                try:
                    chat = await event.get_chat()

                    # فقط پیوی
                    if not hasattr(chat, "title"):

                        parts = clean_text.split()

                        if len(parts) < 2:
                            await event.reply("❌ آیدی کاربر را بفرست")
                            return

                        username = parts[1].replace("@","")

                        user = await self.client.get_entity(username)
                        user_id = user.id

                        done = False

                        for gid in get_active_groups():
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
                            await event.reply("✅ انجام شد")
                        else:
                            await event.reply("❌ گروهی پیدا نشد")

                        return

                except Exception as e:
                    await event.reply(f"❌ خطا: {e}")
                    return

'''

pos=s.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی")
s=s[:pos]+block+s[pos:]

p.write_text(s)
print("fixed")
PY

python3 -m py_compile main.py && echo ok
