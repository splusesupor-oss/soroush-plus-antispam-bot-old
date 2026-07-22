from pathlib import Path
import shutil

p = Path("main.py")
shutil.copy2(p, "main.py.before_riddle_real_final")

s = p.read_text(encoding="utf-8")

start = s.find("              # RIDDLE_SAFE_INSERTED")
end = s.find("              # ثبت آمار پیام گروه", start)

if start == -1 or end == -1:
    print("❌ riddle block not found")
    exit()

riddle = s[start:end]

# حذف چیستان قدیمی
s = s[:start] + s[end:]

marker = '''              except Exception as e:
                  self.logger.log_error(
                      f"خطای فیلتر گروه: {e}"
                  )
'''

pos = s.find(marker)

if pos == -1:
    print("❌ filter except not found")
    exit()

pos += len(marker)

s = s[:pos] + "\n" + riddle + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ moved")
