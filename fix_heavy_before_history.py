from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

# پیدا کردن heavy ban ها
lines=t.splitlines()

out=[]
skip=False

for l in lines:
    if "HEAVY REPEAT SPAM BAN" in l:
        print("FOUND:",l.strip())

    # جلوگیری از اجرای چندباره ban
    if "await bot.admin_actions.ban_user" in l:
        out.append("                if getattr(bot, '_already_banned', False):")
        out.append("                    return")
        out.append("                bot._already_banned=True")

    out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ heavy ban guard added")
