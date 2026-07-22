python3 - <<'PY'
p="modules/spam_detector.py"

s=open(p,encoding="utf-8").read()

s=s.replace(
"self.spam_score_threshold = 1",
"self.spam_score_threshold = 2"
)

s=s.replace(
"if is_banned:\n            return True, reason_banned",
"if is_banned:\n            return True, reason_banned"
)

open(p,"w",encoding="utf-8").write(s)

print("✅ detector fixed")
PY

python3 -m py_compile modules/spam_detector.py && echo "✅ syntax ok"
