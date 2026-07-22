#!/bin/bash

sed -i 's/group_word_reason = f"کلمه ممنوعه ({word})"/group_word_reason = f"فیلتر گروه ({word})"/' main.py

echo "fixed"
grep -n "group_word_reason" main.py
