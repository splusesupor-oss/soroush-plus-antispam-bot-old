from pathlib import Path

p = Path("modules/anti_attack.py")

p.write_text("""
import time
from collections import defaultdict, deque

class AntiAttack:

    def __init__(self):
        self.users = defaultdict(lambda: deque(maxlen=100))

    def check(self, chat_id, user_id):
        now = time.time()
        key = (chat_id, user_id)

        self.users[key].append(now)

        recent = [
            x for x in self.users[key]
            if now - x <= 3
        ]

        self.users[key] = deque(recent, maxlen=100)

        if len(recent) >= 15:
            return True

        return False
""", encoding="utf-8")

print("✅ anti_attack.py created")
