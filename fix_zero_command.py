from pathlib import Path
import re

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''username = None
                          group_link = None'''

new = '''username = None
                          group_id = None'''

s = s.replace(old, new)

old2 = '''if "splus.ir" in line:
                                  group_link = line'''

new2 = '''m2 = re.search(r"\\\\b(\\\\d{5,})\\\\b", text)
                          if m2:
                              group_id = int(m2.group(1))'''

s = s.replace(old2, new2)

old3 = '''if username and group_link:'''

new3 = '''if username and group_id:'''

s = s.replace(old3, new3)

old4 = '''group = None
                              user = await self.client.get_entity(username)

                              async for d in self.client.iter_dialogs():
                                  if hasattr(d.entity, "title"):
                                      group = d.entity
                                      break

                              if group and user:
                                  self.tracker.reset_count(
                                      group.id,
                                      user.id
                                  )

                                  await self.client.send_message(
                                      group.id,
                                      f"✅ تخلفات @{username} توسط مدیریت صفر شد"
                                  )'''

new4 = '''user = await self.client.get_entity(username)

                              self.tracker.reset_count(
                                  group_id,
                                  user.id
                              )

                              await event.reply(
                                  f"✅ تخلفات @{username} در گروه {group_id} صفر شد"
                              )'''

s = s.replace(old4, new4)

p.write_text(s, encoding="utf-8")
print("✅ دستور صفر با شناسه گروه اصلاح شد")
