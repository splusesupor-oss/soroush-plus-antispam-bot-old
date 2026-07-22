from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

backup = p.with_name("message_handler.before_force_history_delete")
shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

start = -1
end = -1

for i,line in enumerate(lines):
    if "BAN FROM HISTORY" in line:
        start = i
        break

if start == -1:
    print("❌ marker not found")
    print("backup:", backup)
    exit()

for j in range(start, min(start+30,len(lines))):
    if lines[j].strip().startswith("return"):
        end = j+1
        break

if end == -1:
    end = start+20

new = '''
                  print(f"🚨 HISTORY SPAM DELETE ALL | chat={chat_id} user={user_id}")

                  try:
                      ids = get_message_ids(chat_id, user_id)

                      print("🗑️ DELETE ALL COUNT:", len(ids))

                      for i in range(0, len(ids), 100):
                          batch = ids[i:i+100]

                          try:
                              await bot.client.delete_messages(
                                  chat_id,
                                  batch
                              )
                          except Exception as ex:
                              print("DELETE BATCH ERROR:", ex)

                      clear_user(chat_id, user_id)

                  except Exception as ex:
                      print("HISTORY DELETE ERROR:", ex)

                  try:
                      await bot.admin_actions.ban_user(
                          chat_id,
                          user_id
                      )
                      print("🚫 HISTORY USER BANNED")

                  except Exception as ex:
                      print("BAN ERROR:", ex)

                  return
'''.splitlines()

lines = lines[:start] + new + lines[end:]

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ history delete force fixed")
print("backup:",backup)
