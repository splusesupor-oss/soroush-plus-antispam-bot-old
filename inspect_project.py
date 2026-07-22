from pathlib import Path
import re

FILES = [
    "handlers/message_handler.py",
    "core/bot_working_split_ok.py",
]

MODULES = [
    "modules/spam_detector.py",
    "modules/user_tracker.py",
    "modules/banned_storage.py",
    "modules/group_stats.py",
    "modules/security/security_manager.py",
    "modules/security/attack_guard.py",
    "modules/security/delete_queue.py",
    "modules/security/media_spam.py",
]

KEYWORDS = {
    "Anti Attack": [
        "check_attack",
        "attack_guard",
        "ATTACK_HISTORY"
    ],
    "Delete Queue": [
        "add_delete",
        "process_delete",
        "remove_message"
    ],
    "Media Spam": [
        "check_media_spam",
        "clear_media",
        "media_spam"
    ],
    "Security Manager": [
        "check_security",
        "security_manager"
    ],
    "Spam Detector": [
        "SpamDetector",
        "is_spam",
        "analyze"
    ],
    "Repeat Spam": [
        "is_repeat",
        "remember_spam_message",
        "delete_all_spam_messages"
    ],
    "Flood Control": [
        "flood_messages"
    ],
    "Banned Users": [
        "is_banned",
        "add_banned",
        "remove_banned"
    ],
    "Mute": [
        "mute_user",
        "unmute_user"
    ],
    "Ban": [
        "ban_user",
        "unban_user"
    ],
    "Word Filter": [
        "banned_words",
        "check_banned_words"
    ],
    "Delete Messages": [
        "delete_messages"
    ],
    "Games": [
        "new_riddle",
        "new_fill",
        "check_answer"
    ],
    "Admin Commands": [
        "handle_admin_commands"
    ],
}

print("="*60)
print("PROJECT STATUS")
print("="*60)

for f in MODULES:
    p = Path(f)
    print(f"[{'OK' if p.exists() else 'NO'}] {f}")

print("\n" + "="*60)
print("FEATURES")
print("="*60)

text = ""
for f in FILES + MODULES:
    p = Path(f)
    if p.exists():
        try:
            text += p.read_text(encoding="utf-8", errors="ignore")
        except:
            pass

for feature, words in KEYWORDS.items():
    found = any(w in text for w in words)
    print(f"[{'YES' if found else 'NO '}] {feature}")

print("\n" + "="*60)
print("EVENT HANDLERS")
print("="*60)

for f in FILES:
    p = Path(f)
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    handlers = re.findall(r'async def ([A-Za-z0-9_]+)', t)
    print(f"\n{f}")
    for h in handlers:
        print(" -", h)

print("\n" + "="*60)
print("DONE")
