from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").replace("\t","    ").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if l.strip() == "# بررسی تکرار شدید داخل یک پیام":
        start = i
    if start is not None and l.strip() == "group_word_spam = False":
        end = i
        break

if start is None or end is None:
    print("❌ markers not found")
    exit()

block = [
"          # بررسی تکرار شدید داخل یک پیام",
"          try:",
"              import re",
"",
"              words = re.findall(r'\\w+|[آ-ی]+', message_text.lower())",
"              repeat_found = False",
"",
"              for w in set(words):",
"                  if len(w) >= 3 and words.count(w) >= 8:",
"                      repeat_found = True",
"                      break",
"",
"              if repeat_found:",
"                  from modules.user_map import save_user",
"                  save_user(chat_id, username, user_id)",
"",
"                  print('🚨 HEAVY REPEAT SPAM:', username, user_id)",
"",
"                  return",
"",
"          except Exception as e:",
"              print('خطای بررسی تکرار شدید:', e)",
""
]

lines = lines[:start] + block + lines[end:]

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ heavy block normalized")
