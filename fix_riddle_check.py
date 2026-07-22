from pathlib import Path

p = Path("modules/riddles.py")
s = p.read_text(encoding="utf-8")

old = '''        if answer.strip() == data['answer']:
            del active_riddles[key]
            return True
'''

new = '''        user_answer = answer.strip().replace("ي", "ی").replace("ك", "ک").replace(" ", "")
        correct_answer = data['answer'].strip().replace("ي", "ی").replace("ك", "ک").replace(" ", "")

        if user_answer == correct_answer:
            del active_riddles[key]
            return True
'''

if old in s:
    s = s.replace(old, new, 1)
    print("✅ بررسی جواب چیستان بهتر شد")
else:
    print("❌ بخش پیدا نشد")

p.write_text(s, encoding="utf-8")
