#!/bin/bash
cd "$(dirname "$0")"

cp main.py main_before_warning_limit_fix.py

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''count=count,
                          threshold=self.config_manager.get("spam_threshold", 3),'''

new='''count=min(
                              count,
                              self.config_manager.get("spam_threshold", 5)
                          ),
                          threshold=self.config_manager.get("spam_threshold", 5),'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("warning counter fixed")
else:
    print("target not found")

PY

python3 -m py_compile main.py && echo "syntax ok"
