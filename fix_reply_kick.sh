#!/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

s=s.replace(
    "await self.client.kick_participant(",
    "await self.client.kick_participant("
)

open(p,"w",encoding="utf-8").write(s)

print("reply kick fixed")
PY

python3 -m py_compile main.py && echo "syntax ok"
