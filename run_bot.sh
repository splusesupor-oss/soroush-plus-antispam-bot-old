#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

while true
do
    pkill -f "python3 main.py"
    sleep 2
    python3 main.py
    echo "BOT CRASH - RESTART"
    sleep 5
done
