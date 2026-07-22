#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")/.."

python3 -m py_compile handlers/message_handler.py

if [ $? -eq 0 ]; then
    echo "✅ message_handler.py OK"
else
    echo "❌ compile error"
fi
