#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

pkill -f "python3 main.py" 2>/dev/null

sleep 2

while true
do
    echo "🚀 Starting bot..."
    python3 main.py

    echo "⚠️ Bot stopped - restarting in 5 seconds..."
    sleep 5
done
