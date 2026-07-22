#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

while true
do
echo "=== BOT START ==="
python3 main.py
echo "=== BOT CRASHED ==="
sleep 5
done
