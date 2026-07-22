from pathlib import Path
import ast

f = Path("handlers/message_handler.py")

print("="*60)
print("FILE:", f)
print("="*60)

text = f.read_text(encoding="utf-8")

print("\nFunctions:\n")

try:
    tree = ast.parse(text)
    funcs = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((n.lineno, n.name))
    for l,n in sorted(funcs):
        print(f"{l:5}  {n}")
except Exception as e:
    print("AST ERROR:", e)

print("\nChecks:\n")

checks = [
    "handle_new_message",
    "get_activation_admin_info",
    "handle_admin_commands",
    "activate_group",
    "deactivate_group",
    "admins_text",
    'if clean_text in ["فعال سازی", "غیر فعال"]',
]

for c in checks:
    cnt=text.count(c)
    print(f"{cnt:2}x  {c}")

print("\nDuplicate activation blocks:")

for i,l in enumerate(text.splitlines(),1):
    if 'if clean_text in ["فعال سازی", "غیر فعال"]' in l:
        print(i)

print("\nSyntax:")

try:
    compile(text,str(f),"exec")
    print("OK")
except Exception as e:
    print(e)

