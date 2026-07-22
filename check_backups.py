from pathlib import Path
import subprocess

files=list(Path("handlers").glob("message_handler*"))

for f in files:
    try:
        r=subprocess.run(
            ["python3","-m","py_compile",str(f)],
            capture_output=True,
            text=True
        )
        if r.returncode==0:
            print("✅ سالم:", f)
        else:
            print("❌ خراب:", f)
    except Exception as e:
        print(e)
