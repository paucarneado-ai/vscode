#!/usr/bin/env bash
# check.sh — Run all verification checks before deploy or merge.
# Usage: bash scripts/check.sh
set -uo pipefail

PASS=0
FAIL=0
TOTAL=3

step() {
  local label="$1"
  shift
  echo ""
  echo "=== [$label] ==="
  if "$@"; then
    echo "  OK  $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $label"
    FAIL=$((FAIL + 1))
  fi
}

step "Unit tests (158)" \
  python -m pytest tests/api/test_api.py -q --tb=short

step "Smoke tests (7)" \
  python -m pytest tests/e2e/test_smoke.py -q --tb=short

step "Semgrep (4 rules)" \
  semgrep --config .semgrep/ --no-git-ignore --quiet

echo ""
echo "=== Results: ${PASS}/${TOTAL} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
