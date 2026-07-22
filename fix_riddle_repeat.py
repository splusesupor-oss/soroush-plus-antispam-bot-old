from pathlib import Path
import shutil

p = Path("modules/riddles.py")
backup = "modules/riddles.py.before_repeat_fix"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

s = s.replace(
"""active_riddles = {}
RIDDLE_TIMEOUT = 50
""",
"""active_riddles = {}
used_riddles = set()
RIDDLE_TIMEOUT = 50
"""
)

s = s.replace(
"""def new_riddle(chat_id, user_id):
    q, a = random.choice(RIDDLES)
    active_riddles[(chat_id, user_id)] = {
        'answer': a,
        'time': time.time()
    }
    return q
""",
"""def new_riddle(chat_id, user_id):
    global used_riddles

    if len(used_riddles) >= len(RIDDLES):
        used_riddles.clear()

    available = [
        r for i, r in enumerate(RIDDLES)
        if i not in used_riddles
    ]

    index = random.randrange(len(available))
    q, a = available[index]

    real_index = RIDDLES.index((q, a))
    used_riddles.add(real_index)

    active_riddles[(chat_id, user_id)] = {
        'answer': a,
        'time': time.time()
    }

    return q
"""
)

p.write_text(s, encoding="utf-8")

print("✅ تکراری شدن چیستان اصلاح شد")
print("📦 بکاپ:", backup)
