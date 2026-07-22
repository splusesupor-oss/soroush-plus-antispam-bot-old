"""
ماژول لاگ‌گیری پیام‌های حذف شده
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional

class BotLogger:
    def __init__(self, log_file: str = "logs/deleted_messages.log", console_log: bool = True):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)

        # Logger برای کنسول
        self.logger = logging.getLogger("SoroushAntiSpam")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

            if console_log:
                ch = logging.StreamHandler()
                ch.setFormatter(formatter)
                self.logger.addHandler(ch)

            # فایل لاگ عمومی
            fh = logging.FileHandler("logs/bot.log", encoding='utf-8')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

    def log_deleted_message(self, user_id: int, username: Optional[str], group_id: int, 
                            group_title: Optional[str], original_text: str, reason: str,
                            message_id: Optional[int] = None):
        """ثبت لاگ پیام حذف شده به صورت JSON Lines"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_persian": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "username": username,
            "group_id": group_id,
            "group_title": group_title,
            "message_id": message_id,
            "original_text": original_text[:1000],  # محدود کردن طول
            "reason": reason
        }

        # نوشتن در فایل مخصوص حذف شده‌ها
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # لاگ کنسول
        self.logger.info(f"🗑️ حذف شد | گروه: {group_title}({group_id}) | کاربر: {username}({user_id}) | دلیل: {reason} | متن: {original_text[:80]}...")

    def log_action(self, action: str, user_id: int, group_id: int, details: str = ""):
        """لاگ اقدامات مدیریتی مثل mute/ban"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "group_id": group_id,
            "details": details
        }
        with open("logs/actions.log", 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.logger.warning(f"⚙️ اقدام مدیریتی | {action} | کاربر {user_id} در گروه {group_id} | {details}")

    def log_info(self, message: str):
        self.logger.info(message)

    def log_error(self, message: str):
        self.logger.error(message)
