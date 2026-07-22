import cProfile
import pstats
import subprocess
import sys

cmd = [sys.executable, "main.py"]

prof = cProfile.Profile()
prof.enable()

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    pass

prof.disable()

prof.dump_stats("bot.prof")

print("\n========== TOP 100 ==========\n")
p = pstats.Stats("bot.prof")
p.sort_stats("cumtime").print_stats(100)
