#!/usr/bin/env python3
"""
repair_message_handler.py
=========================
Automatically detects and repairs broken try/except blocks and indentation
in handlers/message_handler.py (Soroush Plus bot).

Specifically fixes the section between:
  "# برسی تکرار شدید داخل یک پیام" (heavy repeat spam detection)
and:
  "group_word_spam = False" (group word filter start)

Features preserved:
  - spam detection
  - history repeat detection
  - heavy repeated spam ban
  - message deletion (bulk batches of 100, 0.2s delay)
  - admin actions
  - group word filters
  - normal message handling
"""

import os
import sys
import shutil
import re
import time


# ─── Configuration ───────────────────────────────────────────────────────────

TARGET_FILE = "handlers/message_handler.py"
BACKUP_SUFFIX = ".backup_before_ai_fix"
MAX_RETRIES = 5

# Marker comments to locate the broken section
MARKER_START = "# برسی تکرار شدید داخل یک پیام"
MARKER_START_ALT = "# برسی تکرار شدید داخل یک پیام"
MARKER_END = "group_word_spam = False"

# The CORRECT replacement block (8-space base indent = inside async def + outer try)
CORRECT_BLOCK = r'''        # برسی تکرار شدید داخل یک پیام
        try:
            import re

            words = re.findall(r"\w+|[آ-ی]+", message_text.lower())
            repeat_found = False

            for w in set(words):
                if len(w) >= 3 and words.count(w) >= 8:
                    repeat_found = True
                    break

            if repeat_found:
                from modules.user_map import save_user

                save_user(chat_id, username, user_id)

                # حذف پیام های قبلی به صورت 100 تایی
                try:
                    ids = get_message_ids(chat_id, user_id)

                    if ids:
                        import asyncio

                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]

                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )
                            except Exception as ex:
                                print("bulk delete error:", ex)

                            await asyncio.sleep(0.2)

                        clear_user(chat_id, user_id)

                    else:
                        await bot.admin_actions.delete_message(
                            chat_id,
                            event=event
                        )

                except Exception as ex:
                    print("history delete error:", ex)

                # Heavy repeat spam ban
                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key = f"{chat_id}:{user_id}"

                if punish_key not in bot.punished_users:
                    bot.punished_users.add(punish_key)

                    await bot.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                return

        except Exception as e:
            print('خطای بررسی تکرار شدید:', e)

'''


# ─── Helpers ─────────────────────────────────────────────────────────────────

def find_marker_line(lines, marker):
    """Find the line index containing the marker text."""
    for i, line in enumerate(lines):
        if marker in line:
            return i
    return -1


def find_section_boundaries(lines):
    """
    Find start and end line indices of the broken section.
    Returns (start_idx, end_idx) or (None, None) if not found.
    """
    start = find_marker_line(lines, MARKER_START)
    if start == -1:
        # Try alternative marker spelling
        start = find_marker_line(lines, MARKER_START_ALT)

    if start == -1:
        return None, None

    # Find the "group_word_spam = False" line after start
    end = -1
    for i in range(start + 1, len(lines)):
        if MARKER_END in lines[i]:
            end = i
            break

    if end == -1:
        return start, None  # Found start but no end marker

    return start, end


def detect_indentation_errors(lines, start, end):
    """
    Analyze the section between start and end for indentation issues.
    Returns a list of problems found.
    """
    problems = []
    section = lines[start:end+1]

    # Check for try without matching except
    try_count = 0
    except_count = 0
    for line in section:
        stripped = line.strip()
        if stripped.startswith("try:") or stripped == "try:":
            try_count += 1
        if stripped.startswith("except") or stripped.startswith("finally:"):
            except_count += 1

    if try_count != except_count:
        problems.append(
            f"Mismatched try/except: {try_count} try blocks vs {except_count} except blocks"
        )

    # Check for inconsistent indentation within the section
    indent_levels = set()
    for line in section:
        if line.strip():  # non-empty
            leading = len(line) - len(line.lstrip())
            indent_levels.add(leading)

    # A healthy section should have consistent indent progression
    # Look for lines that break the expected pattern
    for i, line in enumerate(section):
        stripped = line.strip()
        if not stripped:
            continue
        leading = len(line) - len(line.lstrip())

        # Check if try body is at the same level as try
        if stripped == "try:" and i + 1 < len(section):
            next_nonempty = None
            for j in range(i + 1, len(section)):
                if section[j].strip():
                    next_nonempty = section[j]
                    break
            if next_nonempty:
                next_indent = len(next_nonempty) - len(next_nonempty.lstrip())
                try_indent = len(line) - len(line.lstrip())
                if next_indent <= try_indent:
                    problems.append(
                        f"Line {start+i+1}: try body not indented "
                        f"(try at {try_indent}, body at {next_indent})"
                    )

    return problems


def attempt_direct_fix(lines, start, end):
    """
    Try to fix the section by replacing the broken block entirely.
    Returns the fixed lines or None if can't fix.
    """
    # Build new content: everything before the section + correct block + everything after
    before = lines[:start]
    after = lines[end+1:]  # everything after the group_word_spam line

    # Always ensure group_word_spam and group_word_reason are initialized
    # at the correct indentation level (8 spaces = inside function + outer try)
    has_group_spam_init = False
    has_group_reason_init = False

    for line in after[:10]:
        # Check for TOP-LEVEL initialization (8 spaces, not inside an if)
        stripped = line.strip()
        if stripped.startswith("group_word_spam") and "=" in stripped:
            indent = len(line) - len(line.lstrip())
            if indent == 8:
                has_group_spam_init = True
        if stripped.startswith("group_word_reason") and "=" in stripped:
            indent = len(line) - len(line.lstrip())
            if indent == 8:
                has_group_reason_init = True

    # Reconstruct
    new_lines = before
    new_lines.append(CORRECT_BLOCK)

    # Add missing initializations at correct indentation
    if not has_group_spam_init:
        new_lines.append("        group_word_spam = False\n")
    if not has_group_reason_init:
        new_lines.append("        group_word_reason = None\n")

    new_lines.extend(after)

    return new_lines


def compile_check(filepath):
    """Check if the file compiles. Returns (success, error_message)."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", filepath],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return True, ""
    else:
        return False, result.stderr.strip()


def try_ast_fix(filepath):
    """
    Last resort: attempt to fix using AST-based analysis.
    Reads the file, finds unbalanced try/except, and attempts correction.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)

    # Find all try/except pairs and check balance
    # Simple approach: find "try:" lines and their matching "except"
    fix_applied = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "try:" or stripped.startswith("try:"):
            # Count indentation of this try
            try_indent = len(line) - len(line.lstrip())

            # Look for matching except/finally at same indent
            found_match = False
            for j in range(i + 1, min(i + 500, len(lines))):
                next_stripped = lines[j].strip()
                next_indent = len(lines[j]) - len(lines[j].lstrip()) if next_stripped else 999

                if next_stripped.startswith("except") and next_indent == try_indent:
                    found_match = True
                    break
                if next_stripped.startswith("finally:") and next_indent == try_indent:
                    found_match = True
                    break
                # If we hit another try at same indent or less, stop
                if (next_stripped == "try:" or next_stripped.startswith("try:")) and next_indent <= try_indent and j != i:
                    break

            if not found_match:
                # This try has no matching except - find the right place to add one
                # Look for a suitable insertion point
                print(f"  ⚠️  Unmatched try at line {i+1}, indent={try_indent}")

                # Find end of try body (look for dedent)
                body_end = i + 1
                for j in range(i + 1, min(i + 500, len(lines))):
                    next_stripped = lines[j].strip()
                    if not next_stripped:
                        body_end = j
                        continue
                    next_indent = len(lines[j]) - len(lines[j].lstrip())
                    if next_indent <= try_indent:
                        body_end = j
                        break
                    body_end = j

                # Insert except block
                except_line = " " * try_indent + "except Exception as e:\n"
                error_line = " " * (try_indent + 4) + "print('خطای بررسی تکرار شدید:', e)\n"
                lines.insert(body_end, except_line)
                lines.insert(body_end + 1, error_line)
                fix_applied = True
                break

    if fix_applied:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return fix_applied


# ─── Main Repair Logic ───────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🔧 message_handler.py Repair Script")
    print("   Soroush Plus Bot - Indentation & Try/Except Fixer")
    print("=" * 60)
    print()

    # ── Step 1: Verify file exists ──
    if not os.path.isfile(TARGET_FILE):
        print(f"❌ فایل پیدا نشد: {TARGET_FILE}")
        print("   لطفاً فایل را در مسیر صحیح قرار دهید.")
        sys.exit(1)

    print(f"📁 فایل هدف: {TARGET_FILE}")
    file_size = os.path.getsize(TARGET_FILE)
    print(f"   اندازه: {file_size:,} بایت")

    # ── Step 2: Create backup ──
    backup_path = TARGET_FILE + BACKUP_SUFFIX
    shutil.copy2(TARGET_FILE, backup_path)
    print(f"\n📦 بکاپ ایجاد شد: {backup_path}")

    # ── Step 3: Initial compile check ──
    print("\n🔍 بررسی اولیه کامپایل...")
    success, error = compile_check(TARGET_FILE)
    if success:
        print("✅ فایل قبلاً بدون خطا کامپایل می‌شود!")
        print("   هیچ تعمیری لازم نیست.")
        print(f"\n📦 مسیر بکاپ: {backup_path}")
        print("✅ message_handler.py repaired successfully")
        return

    print(f"❌ خطای کامپایل:\n   {error}")

    # ── Step 4: Read and analyze ──
    print("\n📖 خواندن فایل و تحلیل ساختار...")
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    print(f"   تعداد خطوط: {total_lines}")

    # ── Step 5: Locate broken section ──
    print("\n🔎 جستجوی بخش آسیب‌دیده...")
    start, end = find_section_boundaries(lines)

    if start is not None:
        print(f"   ✅ نشانگر شروع پیدا شد: خط {start + 1}")
        if end is not None:
            print(f"   ✅ نشانگر پایان پیدا شد: خط {end + 1}")

            # ── Step 6: Analyze problems ──
            print("\n🔬 تحلیل مشکلات...")
            problems = detect_indentation_errors(lines, start, end)
            for p in problems:
                print(f"   ⚠️  {p}")

            if not problems:
                print("   ⚠️  مشکل خاصی تشخیص داده نشد، اما فایل کامپایل نمی‌شود.")
                print("   🔄 جایگزینی کل بخش آسیب‌دیده...")

            # ── Step 7: Apply fix ──
            print("\n🔧 اعمال تعمیر...")
            fixed_lines = attempt_direct_fix(lines, start, end)

            if fixed_lines is not None:
                with open(TARGET_FILE, "w", encoding="utf-8") as f:
                    f.writelines(fixed_lines)
                print("   ✅ بخش آسیب‌دیده بازسازی شد.")
            else:
                print("   ❌ بازسازی مستقیم ممکن نیست.")
        else:
            print(f"   ⚠️  نشانگر پایان پیدا نشد.")
            print("   🔄 تلاش برای تعمیر بر اساس الگوی try/except...")

            # Try AST-based fix
            if try_ast_fix(TARGET_FILE):
                print("   ✅ تعمیر AST-based اعمال شد.")
                # Re-read lines
                with open(TARGET_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                print("   ❌ تعمیر خودکار ممکن نیست.")
    else:
        print("   ⚠️  نشانگر شروع پیدا نشد.")
        print("   🔄 تلاش برای تعمیر عمومی try/except...")

        # Try AST-based fix on whole file
        if try_ast_fix(TARGET_FILE):
            print("   ✅ تعمیر عمومی اعمال شد.")
        else:
            print("   ❌ تعمیر خودکار ممکن نیست.")

    # ── Step 8: Compile verification with retry ──
    print("\n🔄 بررسی کامپایل...")
    for attempt in range(1, MAX_RETRIES + 1):
        success, error = compile_check(TARGET_FILE)
        if success:
            print(f"   ✅ کامپایل موفق در تلاش {attempt}")
            break

        print(f"   ❌ تلاش {attempt}: {error}")

        # Analyze the new error and try to fix
        if "IndentationError" in error or "SyntaxError" in error:
            print(f"   🔧 تلاش برای تعمیر مجدد...")

            # Try to extract line number from error
            line_match = re.search(r'line (\d+)', error)
            if line_match:
                error_line = int(line_match.group(1))
                print(f"      خط مشکل‌دار: {error_line}")

                with open(TARGET_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Re-try section detection
                s, e = find_section_boundaries(lines)
                if s is not None and e is not None:
                    fixed = attempt_direct_fix(lines, s, e)
                    if fixed:
                        with open(TARGET_FILE, "w", encoding="utf-8") as f:
                            f.writelines(fixed)
                        print("      ✅ بخش بازسازی شد.")
                    else:
                        print("      ❌ بازسازی مجدد ممکن نیست.")
                        break
                else:
                    # Try generic AST fix
                    if try_ast_fix(TARGET_FILE):
                        print("      ✅ تعمیر عمومی اعمال شد.")
                    else:
                        print("      ❌ تعمیر مجدد ممکن نیست.")
                        break
            else:
                # Can't parse line number, try generic fix
                if try_ast_fix(TARGET_FILE):
                    print("      ✅ تعمیر عمومی اعمال شد.")
                else:
                    print("      ❌ تعمیر مجدد ممکن نیست.")
                    break
        else:
            print("   ❌ نوع خطای غیرمنتظره، تعمیر خودکار ممکن نیست.")
            break

    # ── Step 9: Final result ──
    print()
    success, error = compile_check(TARGET_FILE)
    if success:
        print("=" * 60)
        print("✅ message_handler.py repaired successfully")
        print("=" * 60)
        print(f"\n📦 مسیر بکاپ: {backup_path}")
        print(f"📁 فایل تعمیر شده: {TARGET_FILE}")

        # Show diff summary
        with open(backup_path, "r", encoding="utf-8") as f:
            old_lines = f.readlines()
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            new_lines = f.readlines()

        old_count = len(old_lines)
        new_count = len(new_lines)
        print(f"\n📊 خلاصه تغییرات:")
        print(f"   خطوط قبل: {old_count}")
        print(f"   خطوط بعد: {new_count}")
        print(f"   تغییر خطوط: {abs(new_count - old_count)}")

        # Verify key features are present
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        features = [
            ("تشخیص اسپم", "is_spam"),
            ("تکرار تاریخچه", "is_repeat"),
            ("بن تکرار شدید", "HEAVY REPEAT SPAM BAN"),
            ("حذف پیام", "delete_message"),
            ("عملیات ادمین", "admin_actions"),
            ("فیلتر کلمات گروه", "group_word_spam"),
            ("بچ‌حذف ۱۰۰تایی", "batch"),
            ("تأخیر ۰.۲ ثانیه", "asyncio.sleep(0.2)"),
            ("حذف تاریخچه", "clear_user"),
            ("بن کاربر", "punish_user"),
            ("جلوگیری بن تکراری", "punished_users"),
        ]

        print(f"\n🛡️ بررسی ویژگی‌ها:")
        all_ok = True
        for name, keyword in features:
            if keyword in content:
                print(f"   ✅ {name}")
            else:
                print(f"   ❌ {name} - پیدا نشد!")
                all_ok = False

        if all_ok:
            print(f"\n🎉 تمام ویژگی‌ها حفظ شده‌اند.")
    else:
        print("=" * 60)
        print("❌ تعمیر ناموفق بود!")
        print("=" * 60)
        print(f"\nآخرین خطای کامپایل:\n   {error}")
        print(f"\n📦 بکاپ در مسیر زیر موجود است: {backup_path}")
        print("   می‌توانید فایل اصلی را بازگردانی کنید.")
        sys.exit(1)


if __name__ == "__main__":
    main()
