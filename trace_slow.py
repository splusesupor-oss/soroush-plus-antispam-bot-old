import time
import sys

def profile(frame,event,arg):
    if event=="call":
        frame.f_locals["_t"]=time.perf_counter()

    elif event=="return":
        st=frame.f_locals.get("_t")
        if st:
            dt=(time.perf_counter()-st)*1000
            if dt>50:
                print(f"{dt:8.1f} ms | {frame.f_code.co_filename}:{frame.f_lineno} | {frame.f_code.co_name}")

    return profile

sys.setprofile(profile)

import main
