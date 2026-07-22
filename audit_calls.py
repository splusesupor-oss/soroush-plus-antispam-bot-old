from pathlib import Path

txt = Path("handlers/message_handler.py").read_text(errors="ignore")

for key in [
    "save_user(",
    "log_deleted_message(",
    "tracker.increment(",
    "send_warning(",
]:
    print("\n" + "="*80)
    print(key)
    i = 0
    while True:
        p = txt.find(key, i)
        if p == -1:
            break
        line = txt.count("\n", 0, p) + 1
        print("line", line)
        print(txt[p-180:p+220])
        i = p + 1
