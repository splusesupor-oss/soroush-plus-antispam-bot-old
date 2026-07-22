#!/bin/bash

cp config/banned_words.txt config/banned_words_backup_before_split.txt

sed -i '/splus\.ir/d' config/banned_words.txt

echo "removed from global banned words"

grep -n "splus.ir" config/banned_words.txt || echo "splus.ir not found"
