#!/data/data/com.termux/files/usr/bin/bash

mkdir -p ../history_fix_backup
mkdir -p ../history_fix_scripts

cp ../handlers/message_handler.py ../history_fix_backup/message_handler_$(date +%Y%m%d_%H%M%S).py

echo "✅ backup created"

cat > ../history_fix_scripts/check_compile.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ..
python3 -m py_compile handlers/message_handler.py

if [ $? -eq 0 ]; then
    echo "✅ message_handler.py OK"
else
    echo "❌ compile error"
fi
EOF

chmod +x ../history_fix_scripts/check_compile.sh

echo "✅ repair folders created"
echo "Run:"
echo "bash history_fix_scripts/check_compile.sh"
