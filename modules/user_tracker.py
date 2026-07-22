"""
ردیاب تعداد هرزنامه‌های هر کاربر + مدیریت وضعیت mute/ban
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict
from collections import defaultdict

class UserTracker:
    def __init__(self, spam_counts_file: str = "logs/spam_counts.json", threshold: int = 3):
        self.spam_counts_file = spam_counts_file
        self.threshold = threshold
        self.spam_counts: Dict[str, Dict[str, int]] = {}  # {group_id: {user_id: count}}
        self.muted_users: Dict[str, datetime] = {}  # برای پیگیری زمان mute
        self.banned_users: Dict[str, datetime] = {}  # برای پیگیری وضعیت ban
        os.makedirs(os.path.dirname(spam_counts_file) if os.path.dirname(spam_counts_file) else ".", exist_ok=True)
        self.load()

    def load(self):
        if os.path.exists(self.spam_counts_file):
            try:
                with open(self.spam_counts_file, 'r', encoding='utf-8') as f:
                    self.spam_counts = json.load(f)
            except:
                self.spam_counts = {}
        else:
            self.spam_counts = {}

    def save(self):
        with open(self.spam_counts_file, 'w', encoding='utf-8') as f:
            json.dump(self.spam_counts, f, ensure_ascii=False, indent=2)

    def _key(self, group_id, user_id):
        return str(group_id), str(user_id)


    def set_muted(self, group_id: int, user_id: int, until: datetime):
        """ثبت کاربر mute شده"""
        key = f"{group_id}:{user_id}"
        self.muted_users[key] = until

    def is_muted(self, group_id: int, user_id: int) -> bool:
        """بررسی وضعیت mute"""
        key = f"{group_id}:{user_id}"
        if key not in self.muted_users:
            return False
        if datetime.now() >= self.muted_users[key]:
            del self.muted_users[key]
            return False
        return True

    def set_banned(self, group_id: int, user_id: int):
        """ثبت کاربر ban شده"""
        key = f"{group_id}:{user_id}"
        self.banned_users[key] = datetime.now()

    def is_banned(self, group_id: int, user_id: int) -> bool:
        """بررسی وضعیت ban"""
        return f"{group_id}:{user_id}" in self.banned_users

    def increment(self, group_id: int, user_id: int) -> int:
        """افزایش شمارنده هرزنامه و برگرداندن تعداد جدید"""
        g_key, u_key = self._key(group_id, user_id)
        if g_key not in self.spam_counts:
            self.spam_counts[g_key] = {}
        if u_key not in self.spam_counts[g_key]:
            self.spam_counts[g_key][u_key] = 0
        
        self.spam_counts[g_key][u_key] += 1
        self.save()
        return self.spam_counts[g_key][u_key]

    def get_count(self, group_id: int, user_id: int) -> int:
        g_key, u_key = self._key(group_id, user_id)
        return self.spam_counts.get(g_key, {}).get(u_key, 0)

    def should_punish(self, group_id: int, user_id: int) -> bool:
        """آیا کاربر باید مجازات شود (بیش از آستانه)"""
        return self.get_count(group_id, user_id) >= self.threshold

    def reset_count(self, group_id: int, user_id: int):
        g_key, u_key = self._key(group_id, user_id)
        if g_key in self.spam_counts and u_key in self.spam_counts[g_key]:
            del self.spam_counts[g_key][u_key]
            self.save()

    def reset_group(self, group_id: int):
        g_key = str(group_id)
        if g_key in self.spam_counts:
            del self.spam_counts[g_key]
            self.save()

    def get_all_counts(self, group_id: int = None):
        if group_id is None:
            return self.spam_counts
        return self.spam_counts.get(str(group_id), {})

    def get_top_spammers(self, group_id: int = None, limit: int = 10):
        """لیست بیشترین اسپمرها"""
        if group_id:
            group_data = self.spam_counts.get(str(group_id), {})
            sorted_users = sorted(group_data.items(), key=lambda x: x[1], reverse=True)
            return sorted_users[:limit]
        else:
            # در کل گروه‌ها
            total = defaultdict(int)
            for g, users in self.spam_counts.items():
                for u, c in users.items():
                    total[u] += c
            return sorted(total.items(), key=lambda x: x[1], reverse=True)[:limit]
