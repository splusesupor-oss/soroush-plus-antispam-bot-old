from pathlib import Path

src = Path("core/bot_before_module.py")
dst = Path("core/bot_working_split_ok.py")

source = src.read_text(encoding="utf-8")
target = dst.read_text(encoding="utf-8")

start = source.index("# آزاد کردن کاربر محروم شده از لیست")
end = source.index("# سکوت کاربر با ریپلای", start)

block = source[start:end]

# اصلاح ChatBannedRights
block = block.replace(
'''banned_rights=types.ChatBannedRights(
                                                                           until_date=None
                         )''',
'''banned_rights=types.ChatBannedRights(
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
                )'''
)

if "if clean_text == \"آزاد\":" in target:
    print("⚠️ قبلا وجود دارد")
else:
    pos = target.find("# سکوت کاربر با ریپلای")

    if pos == -1:
        print("❌ محل قرار دادن پیدا نشد")
    else:
        target = target[:pos] + block + "\n" + target[pos:]
        dst.write_text(target, encoding="utf-8")
        print("✅ دستور آزاد به فایل فعال اضافه شد")
