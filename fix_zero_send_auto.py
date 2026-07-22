from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''                            try:
                                group_entity = await self.client.get_input_entity(int(group_id))
                                await self.client.send_message(
                                    group_entity,
                                    f"✅ تخلفات @{username} صفر شد"
                                )
                            except Exception as send_err:
                                self.logger.log_error(
                                    f"خطای ارسال پیام صفر کردن: {send_err}"
                                )
'''

new = '''                            try:
                                await self.client.send_message(
                                    int(group_id),
                                    f"✅ تخلفات @{username} صفر شد"
                                )
                            except Exception as send_err:
                                self.logger.log_error(
                                    f"خطای ارسال پیام صفر کردن: {send_err}"
                                )
'''

if old not in s:
    raise SystemExit("target not found")

p.write_text(s.replace(old, new), encoding="utf-8")
print("done")
