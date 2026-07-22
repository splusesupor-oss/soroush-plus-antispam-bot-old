from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=1288
end=1306

new=[
"                try:",
"                    await bot.admin_actions.punish_user(",
"                        chat_id,",
"                        user_id,",
"                        username",
"                    )",
"                except Exception as e:",
"                    print('PUNISH ERROR:', e)",
"",
"                return",
"",
"        except Exception as e:",
"            bot.logger.log_error(f'خطای بررسی تکرار داخلی: {e}')",
"",
"        # بررسی فورواردهای محافظت شده",
"        try:",
"            if getattr(event.message, 'fwd_from', None):",
"                fwd = event.message.fwd_from",
"                fwd_id = getattr(getattr(fwd, 'from_id', None), 'channel_id', None)",
"",
"                if fwd_id == 22389465:",
"                    print('✅ فوروارد کانال osine1 محافظت شد')",
"                    return",
]

lines[start:end]=new

p.write_text("\n".join(lines),encoding="utf-8")
print("REPAIRED")
