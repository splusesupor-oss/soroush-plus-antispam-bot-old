#!/bin/bash
# اجرای کل suite تست‌های پروژه، هر تست در یک DATA_DIR ایزوله.
#
#   bash tools/run_all_tests.sh
#
# خروجی نهایی: SUITE_TOTAL / SUITE_PASS / SUITE_FAIL
# گزارش کامل هر تست ناموفق در $REPORT ذخیره می‌شود.
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
REPORT="${REPORT:-$ROOT/.test_report.txt}"
WORK="${WORK:-$ROOT/.test_workdirs}"

rm -rf "$WORK"; mkdir -p "$WORK"
: > "$REPORT"

PASS=0
FAIL=0
FAILED_TESTS=()

for file in tests/test_*.py; do
  name="$(basename "$file" .py)"
  data_dir="$WORK/$name"
  mkdir -p "$data_dir"
  output="$(timeout 240 env \
      PYTHONPATH="$ROOT" \
      SOROUSH_BOT_DATA_DIR="$data_dir" \
      python3 "$file" 2>&1)"
  code=$?
  if [ $code -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "PASS  $file"
  else
    FAIL=$((FAIL + 1))
    FAILED_TESTS+=("$file")
    echo "FAIL  $file (exit=$code)"
    {
      echo "### $file exit=$code"
      echo "$output" | tail -25
      echo
    } >> "$REPORT"
  fi
  rm -rf "$data_dir"
done

rm -rf "$WORK"

echo
echo "===================================================="
echo "SUITE_TOTAL=$((PASS + FAIL))"
echo "SUITE_PASS=$PASS"
echo "SUITE_FAIL=$FAIL"
echo "===================================================="
if [ $FAIL -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED_TESTS[@]}"
  echo "report: $REPORT"
fi
exit $((FAIL > 0))
