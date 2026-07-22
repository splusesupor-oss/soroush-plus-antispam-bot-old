from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=1290
end=1315

new=[
"        # بررسی فورواردهای محافظت شده",
"        try:",
"            if getattr(event.message, 'fwd_from', None):",
"                fwd = event.message.fwd_from",
"                fwd_id = getattr(getattr(fwd, 'from_id', None), 'channel_id', None)",
"",
"                if fwd_id == 22389465:",
"                    print('✅ فوروارد کانال osine1 محافظت شد')",
"                    return",
"",
"        except Exception as e:",
"            print('خطای بررسی فوروارد:', e)",
"",
]

lines[start:end]=new

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED 1310")
