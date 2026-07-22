from pathlib import Path

p = Path("modules/banned_storage.py")
text = p.read_text(encoding="utf-8")

old = '''def remove_banned(group_id, username):
    data = load_banned()
    gid = str(group_id)

    if gid in data and username in data[gid]:
        data[gid].remove(username)
        save_banned(data)
        return True

    return False
'''

new = '''def remove_banned(group_id, username):
    data = load_banned()
    gid = str(group_id)

    if gid not in data:
        return False

    target = str(username).lower()

    for item in list(data[gid]):
        if str(item).lower() == target:
            data[gid].remove(item)
            save_banned(data)
            return True

    return False
'''

if old in text:
    text=text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ banned_storage remove fixed")
else:
    print("⚠️ remove_banned block not found")


# اضافه کردن تابع unban در admin_actions
p=Path("modules/admin_actions.py")
text=p.read_text(encoding="utf-8")

if "def unban_user" not in text:

    insert='''

    async def unban_user(self, chat_id, user_id, username=None):
        try:
            from modules.banned_storage import remove_banned

            target = username or str(user_id)

            remove_banned(chat_id, target)

            user = await self.client.get_entity(user_id)

            await self.client.edit_permissions(
                chat_id,
                user,
                until_date=None,
                view_messages=False,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False,
                send_polls=False,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )

            self.logger.log_action(
                "UNBAN",
                user_id,
                chat_id,
                "رفع بن دائمی"
            )

            return True

        except Exception as e:
            self.logger.log_error(f"خطا در unban {user_id}: {e}")
            return False
'''

    text += insert
    p.write_text(text,encoding="utf-8")
    print("✅ admin_actions unban added")

print("🎯 تمام شد")
