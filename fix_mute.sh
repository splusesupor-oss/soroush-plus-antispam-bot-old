#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

old = '''rights = types.ChatBannedRights(
                  until_date=until_date,
                  send_messages=True,
                  send_media=True,
                  send_stickers=True,
                  send_gifs=True,
                  send_games=True,
                  send_inline=True,
                  send_polls=True
              )'''

new = '''rights = types.ChatBannedRights(
                  until_date=until_date,
                  send_messages=True
              )'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("✅ mute rights fixed")
else:
    print("⚠️ old block not found")

PY

python3 -m py_compile modules/admin_actions.py && echo "✅ syntax ok"
