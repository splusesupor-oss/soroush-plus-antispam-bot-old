from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''try:
                        await self.client.delete_messages(chat_id, ids)
                    except:
                        pass

                    self.flood_messages[user_id] = []

                    print("🚨 اسپمر رگباری:", user_id)

                    try:
                        await self.admin_actions.punish_user(
                            chat_id,
                            user_id,
                            username
                        )
                    except Exception as e:
                        self.logger.log_error(
                            f"خطای ریم اسپمر سریع: {e}"
                        )

                    return'''

new = '''try:
                        await self.client.delete_messages(chat_id, ids)
                    except:
                        pass

                    self.flood_messages[user_id] = []

                    print("🚨 اسپمر رگباری:", user_id)

                    try:
                        removed = await self.admin_actions.punish_user(
                            chat_id,
                            user_id,
                            username
                        )

                        if removed:
                            try:
                                await self.client.send_message(
                                    chat_id,
                                    f"⛔️ کاربر @{username or user_id} به دلیل ارسال اسپم رگباری حذف شد."
                                )
                            except:
                                pass

                    except Exception as e:
                        self.logger.log_error(
                            f"خطای ریم اسپمر سریع: {e}"
                        )

                    return'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("✅ FIX DONE")
else:
    print("❌ بخش پیدا نشد")
