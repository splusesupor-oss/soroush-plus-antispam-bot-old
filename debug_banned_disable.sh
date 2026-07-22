python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

old='''if text == "لغو کلمات ممنوعه":
                disable(chat_id)'''

new='''if text == "لغو کلمات ممنوعه":
                print("DEBUG BANNED DISABLE:", chat_id)
                disable(chat_id)
                print("DEBUG AFTER DISABLE DONE")'''

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("DEBUG PATCH OK")
PY

python3 -m py_compile main.py && echo OK
