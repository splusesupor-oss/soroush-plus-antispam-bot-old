#!/bin/bash

echo "=== moving group filters out of global banned words ==="

for w in سگ کص کر بیو\ چک; do
    sed -i "/^$w$/d" config/banned_words.txt
done

echo "done"

echo "check:"
grep -E "سگ|کص|کر|بیو چک" config/banned_words.txt || echo "not in global banned words"

