from pathlib import Path

p=Path("main.py")
s=p.read_text(encoding="utf-8")

old='''        except Exception as e:
            self.logger.log_error(f"خطای چیستان: {e}")

        except Exception as e:
            self.logger.log_error(f"خطای چیستان: {e}")
'''

new='''        except Exception as e:
            self.logger.log_error(f"خطای چیستان: {e}")
'''

if old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("✅ except تکراری حذف شد")
else:
    print("❌ پیدا نشد")
