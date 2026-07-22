python3 - <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

old = '''await self.client.edit_permissions(
                chat_id,
                user,
                until_date=until_date,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                send_polls=False
            )'''

new = '''await self.client.edit_permissions(
                chat_id,
                user,
                until_date=until_date,
                send_messages=False
            )'''

if old not in s:
    print("OLD NOT FOUND")
else:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("MUTE FIXED")
PY
