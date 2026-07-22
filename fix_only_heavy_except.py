from pathlib import Path

p=Path("handlers/message_handler.py")

text=p.read_text(encoding="utf-8")

old="""                  return


            except Exception as e:
                print('خطای بررسی تکرار شدید:', e)
"""

new="""                  return

          except Exception as e:
              print('خطای بررسی تکرار شدید:', e)
"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ فقط except بخش heavy درست شد")
else:
    print("❌ الگو پیدا نشد")

