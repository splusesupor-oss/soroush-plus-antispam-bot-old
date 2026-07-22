from pathlib import Path
import re

files = [
    "handlers/message_handler.py",
    "modules/spam_detector.py",
    "modules/admin_storage.py",
    "modules/user_map.py",
    "modules/logger_module.py",
]

checks = {
    "ADMIN_BYPASS": [
        "ADMIN BYPASS",
        "is_admin(",
    ],
    "FORWARD_PROTECT": [
        "fwd_from",
        "فوروارد",
    ],
    "GROUP_WORDS": [
        "group_word_spam",
        "get_words",
    ],
    "SPAM_DETECTOR": [
        "is_spam(",
        "repeat_spam",
        "normalized",
    ],
    "SAVE_USER": [
        "save_user(",
    ],
    "LOGGER": [
        "log_deleted_message",
    ],
    "TRACKER": [
        "tracker.increment",
        "tracker.reset_count",
    ],
    "PUNISH": [
        "punish_user",
        "ban_user",
        "mute_user",
    ],
    "DELETE": [
        "delete_message",
        "delete_messages",
    ],
    "WARNING": [
        "send_warning",
    ],
}

for f in files:
    print("="*80)
    print(f)
    p = Path(f)
    if not p.exists():
        print("❌ FILE NOT FOUND")
        continue

    txt = p.read_text(errors="ignore")

    for title, words in checks.items():
        found = []
        for w in words:
            if w in txt:
                found.append(w)

        if found:
            print(f"✅ {title:18} -> {', '.join(found)}")
        else:
            print(f"❌ {title:18} -> MISSING")

print("="*80)

mh = Path("handlers/message_handler.py")
if mh.exists():
    txt = mh.read_text(errors="ignore")

    print("\n===== DUPLICATE CHECK =====")
    for key in [
        "is_admin(",
        "save_user(",
        "log_deleted_message",
        "group_word_spam",
        "repeat_spam",
        "fwd_from",
        "ADMIN BYPASS",
    ]:
        c = txt.count(key)
        print(f"{key:25} {c}")

    print("\n===== TRY/EXCEPT =====")
    print("try     :", len(re.findall(r'^\\s*try\\s*:', txt, re.M)))
    print("except  :", len(re.findall(r'^\\s*except', txt, re.M)))
    print("return  :", txt.count("return"))
