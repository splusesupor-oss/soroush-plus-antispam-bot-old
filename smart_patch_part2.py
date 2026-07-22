from pathlib import Path
import shutil
import py_compile

TARGET = Path("handlers/message_handler.py")
BACKUP = TARGET.with_suffix(".py.smart_backup")


def restore():
    if BACKUP.exists():
        shutil.copy2(BACKUP, TARGET)
        print("Backup restored")


def compile_ok():
    py_compile.compile(str(TARGET), doraise=True)


text = TARGET.read_text(encoding="utf-8")

MARKER = '# اطلاعات پیام'

SECURITY = '''
        # ===== SECURITY MANAGER =====
        try:
            security_result = check_security(
                user_id,
                event.message
            )

            if security_result.get("attack"):
                await remove_message(
                    chat_id,
                    event.message.id
                )
                return

            if security_result.get("media_spam"):
                await remove_message(
                    chat_id,
                    event.message.id
                )
                return

        except Exception as security_error:
            print("security manager:", security_error)
        # ===== END SECURITY =====

'''

if SECURITY.strip() not in text:

    pos = text.find(MARKER)

    if pos == -1:
        print("Marker not found")
        raise SystemExit

    end = text.find("\n", pos)

    text = (
        text[:end + 1]
        + SECURITY
        + text[end + 1:]
    )

TARGET.write_text(text, encoding="utf-8")

try:
    compile_ok()
    print("✅ security injected")

except Exception as e:
    print("Compile failed")
    print(e)
    restore()
