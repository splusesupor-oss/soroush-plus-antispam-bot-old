from pathlib import Path
import importlib
import py_compile

print("=" * 60)
print("🩺 Soroush Plus Bot Health Check")
print("=" * 60)

OK = []
BAD = []

def check(name, condition):
    if condition:
        OK.append(name)
        print("✅", name)
    else:
        BAD.append(name)
        print("❌", name)

# ---------- Files ----------
files = [
    "main.py",
    "core/bot_working_split_ok.py",
    "handlers/message_handler.py",
    "handlers/admin_handler.py",

    "modules/spam_detector.py",
    "modules/user_tracker.py",
    "modules/banned_storage.py",
    "modules/group_stats.py",

    "modules/security/security_manager.py",
    "modules/security/attack_guard.py",
    "modules/security/media_spam.py",
    "modules/security/delete_queue.py",
]

print("\n📁 FILE CHECK")
for f in files:
    check(f, Path(f).exists())


# ---------- Compile ----------
print("\n🐍 PYTHON COMPILE")

for f in files:
    if Path(f).exists() and f.endswith(".py"):
        try:
            py_compile.compile(f, doraise=True)
            check("compile " + f, True)
        except Exception as e:
            check("compile " + f, False)
            print("   ", e)


# ---------- Imports ----------
print("\n📦 MODULE IMPORT CHECK")

imports = [
    "modules.spam_detector",
    "modules.user_tracker",
    "modules.banned_storage",
    "modules.group_stats",
    "modules.security.security_manager",
    "modules.security.attack_guard",
    "modules.security.media_spam",
    "modules.security.delete_queue",
]

for mod in imports:
    try:
        importlib.import_module(mod)
        check("import " + mod, True)
    except Exception as e:
        check("import " + mod, False)
        print("   ", e)


# ---------- Feature Search ----------
print("\n🛡️ FEATURE CHECK")

search_files = ""

for f in files:
    p = Path(f)
    if p.exists():
        search_files += p.read_text(
            encoding="utf-8",
            errors="ignore"
        )

features = {
    "Spam Detector": [
        "SpamDetector",
        "is_spam"
    ],

    "Security Manager": [
        "check_security"
    ],

    "Attack Guard": [
        "check_attack"
    ],

    "Media Spam": [
        "check_media_spam"
    ],

    "Delete Queue": [
        "add_delete",
        "process_delete"
    ],

    "Repeat Spam": [
        "remember_spam_message",
        "is_repeat"
    ],

    "Flood Control": [
        "flood_messages"
    ],

    "Ban System": [
        "is_banned",
        "add_banned"
    ],

    "Mute System": [
        "mute"
    ],

    "Admin Commands": [
        "handle_admin_commands"
    ],

    "Games": [
        "new_riddle",
        "check_answer"
    ]
}


for name, words in features.items():
    found = any(w in search_files for w in words)
    check(name, found)


# ---------- Final ----------
print("\n" + "=" * 60)
print("RESULT")
print("=" * 60)

print("✅ سالم:", len(OK))
print("❌ مشکل:", len(BAD))

if BAD:
    print("\nموارد مشکل:")
    for x in BAD:
        print("-", x)
else:
    print("\n🎉 پروژه از نظر ساختار آماده اجرا است")

print("=" * 60)
