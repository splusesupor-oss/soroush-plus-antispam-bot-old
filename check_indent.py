FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    lines=f.readlines()

for i in range(475,500):
    print(f"{i+1}: {repr(lines[i])}")
