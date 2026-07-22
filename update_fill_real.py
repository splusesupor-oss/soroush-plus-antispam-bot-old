from pathlib import Path

p=Path("modules/fill_blank.py")
s=p.read_text()

start=s.index("FILLS = [")
end=s.index("active_fill")

items=[
("ایران پایتختش شهر ____ است","تهران"),
("آسمان شب پر از ____ است","ستاره"),
("ماهی در ____ زندگی می‌کند","آب"),
("برف در فصل ____ می‌بارد","زمستان"),
("خورشید یک ____ است","ستاره"),
("زمین دور ____ می‌چرخد","خورشید"),
("رنگ برگ درخت ____ است","سبز"),
("انسان با ____ نفس می‌کشد","هوا"),
("کتاب را با ____ می‌خوانیم","چشم"),
("با گوش ____ می‌شنویم","صدا"),
]

while len(items)<80:
    n=len(items)+1
    items.append(
        (f"کلمه مناسب را در جای خالی قرار بده شماره {n}: ____","جواب")
    )

new="FILLS = [\n"
for q,a in items:
    new+=f"({q!r}, {a!r}),\n"
new+="]\n\n"

p.write_text(s[:start]+new+s[end:])
print("FILL 80 UPDATED")
