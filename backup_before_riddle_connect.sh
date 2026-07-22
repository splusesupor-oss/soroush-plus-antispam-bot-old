#!/bin/bash

cp main.py main.py.before_riddle_connect

echo "✅ backup created: main.py.before_riddle_connect"

python3 -m py_compile main.py && echo "✅ current main.py ok"

