from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
skip = False

for i,l in enumerate(lines):
    # اصلاح if فوروارد که بدنه‌اش یک خط پایین‌تر تورفتگی خراب دارد
    if l.strip() == 'if getattr(event.message, "fwd_from", None):':
        out.append(l)
        continue

    if i > 0 and lines[i-1].strip() == 'if getattr(event.message, "fwd_from", None):':
        if l.strip().startswith("await bot.client.delete_messages"):
            out.append("                " + l.strip())
            continue

    # اصلاح if های بعدی داخل همان بخش
    if l.strip().startswith("forward_sender ="):
        out.append("                " + l.strip())
        continue

    out.append(l)

p.write_text("\n".join(out), encoding="utf-8")

print("✅ اصلاح فوروارد انجام شد")
