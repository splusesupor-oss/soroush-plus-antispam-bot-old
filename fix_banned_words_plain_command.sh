python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

old='''            # اجرای دستورات مدیریتی
            if clean_text.startswith(("!", "/", ".")):'''

new='''            # اجرای دستورات مدیریتی
            if clean_text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:
                try:
                    sender = await event.get_sender()
                    await self.handle_admin_commands(
                        event,
                        clean_text,
                        getattr(sender, "id", 0),
                        chat_id
                    )
                    return
                except Exception as e:
                    self.logger.log_error(f"خطای اجرای دستور کلمات ممنوعه: {e}")

            if clean_text.startswith(("!", "/", ".")):'''

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("PLAIN BANNED COMMAND OK")
PY

python3 -m py_compile main.py && echo "MAIN OK"
