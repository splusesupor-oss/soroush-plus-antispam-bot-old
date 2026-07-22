#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

while true
do
    echo "START BOT..."
    python3 main.py

    echo "BOT STOPPED - RESTART AFTER 5 SEC..."
    sleep 5
done
