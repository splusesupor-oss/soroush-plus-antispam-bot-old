FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    lines=f.readlines()

backup=FILE+".bak_lines_help"

with open(backup,"w",encoding="utf-8") as f:
    f.writelines(lines)

# حذف خطوط خراب 417 تا 439 (شماره فایل = شماره نمایش nl)
# در لیست پایتون از صفر شروع می‌شود
start=416
end=439

new=[
"                  )\n",
"                  await event.reply(help_text)\n",
"                  return\n",
"\n"
]

lines = lines[:start] + new + lines[end:]

with open(FILE,"w",encoding="utf-8") as f:
    f.writelines(lines)

print("LINES FIXED")
print("BACKUP:",backup)
