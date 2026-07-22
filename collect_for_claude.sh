#!/data/data/com.termux/files/usr/bin/bash

OUT="claude_files"
mkdir -p "$OUT"

files=(
"handlers/message_handler.py"
"modules/admin_actions.py"
"modules/banned_storage.py"
"modules/spam_detector.py"
"modules/user_tracker.py"
"modules/user_map.py"
"modules/config_manager.py"
"modules/logger_module.py"
)

for f in "${files[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "$OUT/"
        echo "✅ copied $f"
    else
        echo "❌ not found $f"
    fi
done

echo
echo "🔎 Searching related files..."

find . -type f \( \
-name "*ban*" -o \
-name "*spam*" -o \
-name "*punish*" -o \
-name "*track*" -o \
-name "*history*" \
\) -not -path "./__pycache__/*" \
-exec cp {} "$OUT/" \;

echo "✅ Done. Files are in $OUT"
