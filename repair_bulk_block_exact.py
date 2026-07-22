from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

new_block = """                  # حذف گروهی پیام های اسپم از تاریخچه
                  try:
                      ids = get_message_ids(chat_id, user_id)

                      if ids:
                          import asyncio

                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]

                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as ex:
                                  print("bulk delete error:", ex)

                              await asyncio.sleep(0.2)

                          clear_user(chat_id, user_id)

                      else:
                          await bot.admin_actions.delete_message(
                              chat_id,
                              event=event
                          )

                  except Exception as ex:
                      print("history delete error:", ex)""".splitlines()

out=[]

for i,l in enumerate(lines, start=1):
    if 1356 <= i <= 1385:
        if i == 1356:
            out.extend(new_block)
    else:
        out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ only broken bulk section replaced")
