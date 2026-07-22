#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text(encoding="utf-8")

old='''all_counts = self.tracker.get_all_counts()

                          for gid, users in all_counts.items():
                              if str(user_id) in users:
                                  self.tracker.reset_count(int(gid), user_id)
                                  reset_groups.append(gid)'''

new='''all_counts = self.tracker.get_all_counts()

                          for gid, users in all_counts.items():
                              if str(user_id) in users:

                                  # ریست با هر دو فرمت آیدی گروه
                                  self.tracker.reset_count(int(gid), user_id)

                                  try:
                                      if str(gid).startswith("-100"):
                                          self.tracker.reset_count(
                                              int(str(gid).replace("-100","")),
                                              user_id
                                          )
                                      else:
                                          self.tracker.reset_count(
                                              int("-100"+str(gid)),
                                              user_id
                                          )
                                  except:
                                      pass

                                  reset_groups.append(gid)'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("reset fixed")
else:
    print("marker not found")

PY

python3 -m py_compile main.py && echo "syntax ok"
