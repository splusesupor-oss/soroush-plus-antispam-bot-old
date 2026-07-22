python3 - <<'PY'
p="modules/spam_detector.py"
s=open(p,encoding="utf-8").read()

s=s.replace(
"def check_spam_score(self, text: str) -> Tuple[int, List[str]]:",
"def check_spam_score(self, text: str, chat_id=None) -> Tuple[int, List[str]]:"
)

s=s.replace(
"score, reasons = self.check_spam_score(text)",
"score, reasons = self.check_spam_score(text, chat_id)"
)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile modules/spam_detector.py && echo "SPAM SCORE CHATID OK"
