python3 - <<'PY'
p="modules/spam_detector.py"

s=open(p,encoding="utf-8").read()

old='''        if score >= self.spam_score_threshold:
            return True, " و ".join(reasons)

        return False, ""'''

new='''        # جلوگیری از اسپم اشتباه پیام‌های عادی
        # یک قانون تنها نباید اسپم حساب شود
        if score >= 3:
            return True, " و ".join(reasons)

        return False, ""'''

if old not in s:
    print("target not found")
else:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("fixed")

PY

python3 -m py_compile modules/spam_detector.py && echo "syntax ok"
