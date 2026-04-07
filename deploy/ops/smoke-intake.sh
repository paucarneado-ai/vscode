#!/usr/bin/env bash
# smoke-intake.sh — Quick operational smoke test for lead ingestion
#
# STAGING USE: runs by default
# PRODUCTION USE: requires --production flag (creates a real test lead)
#
# Usage:
#   bash smoke-intake.sh                    # staging only (safe)
#   bash smoke-intake.sh --production       # production (creates test lead)
#
# Tests: create lead, dedup, retrieve, score.
# Uses a unique @openclaw-ops.internal email to be easily identifiable/filterable.
set -uo pipefail

API="http://127.0.0.1:8000"
TS=$(date +%s)
EMAIL="smoke-test-${TS}@openclaw-ops.internal"
PASS=0
FAIL=0

ok()   { echo "  OK    $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }

# --- Production safety guard ---
APP_ENV=$(curl -s "${API}/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('env','unknown'))" 2>/dev/null || echo "unknown")

if [ "$APP_ENV" != "development" ] && [ "$APP_ENV" != "test" ]; then
  if [ "${1:-}" != "--production" ]; then
    echo "ERROR: APP_ENV=${APP_ENV} — this is not a dev/test environment."
    echo "Running smoke tests here creates real test leads in the database."
    echo ""
    echo "To proceed: bash smoke-intake.sh --production"
    exit 1
  fi
  echo "WARNING: Running in ${APP_ENV} environment (--production flag set)"
  echo ""
fi

echo "=== Intake smoke test ==="
echo "  env: ${APP_ENV}"
echo "  test email: ${EMAIL}"
echo ""

# 1. Create lead
resp=$(curl -s -w "\n%{http_code}" -X POST "${API}/leads/webhook/ops-smoke" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OPENCLAW_API_KEY:-}" \
  -d "{\"name\":\"Smoke Test ${TS}\",\"email\":\"${EMAIL}\",\"notes\":\"Tipo: Test\"}")
code=$(echo "$resp" | tail -1)
body=$(echo "$resp" | head -1)

if [ "$code" = "200" ]; then
  lead_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('lead_id','?'))" 2>/dev/null || echo "?")
  ok "lead created (id=${lead_id})"
else
  fail "create returned ${code}: ${body}"
  echo ""
  echo "=== $PASS OK, $FAIL FAIL ==="
  exit 1
fi

# 2. Duplicate check
resp2=$(curl -s -w "\n%{http_code}" -X POST "${API}/leads/webhook/ops-smoke" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OPENCLAW_API_KEY:-}" \
  -d "{\"name\":\"Smoke Test ${TS}\",\"email\":\"${EMAIL}\",\"notes\":\"Tipo: Test\"}")
code2=$(echo "$resp2" | tail -1)

if [ "$code2" = "409" ]; then
  ok "duplicate detected (409)"
else
  fail "duplicate returned ${code2} (expected 409)"
fi

# 3. Retrieve
resp3=$(curl -s -w "\n%{http_code}" "${API}/leads/${lead_id}" \
  -H "X-API-Key: ${OPENCLAW_API_KEY:-}")
code3=$(echo "$resp3" | tail -1)
body3=$(echo "$resp3" | head -1)

if [ "$code3" = "200" ]; then
  stored_email=$(echo "$body3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('email',''))" 2>/dev/null || echo "")
  if [ "$stored_email" = "$EMAIL" ]; then
    ok "lead retrievable, email matches"
  else
    fail "lead email mismatch: ${stored_email}"
  fi
else
  fail "lead retrieval returned ${code3}"
fi

# 4. Score
score=$(echo "$body3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('score',0))" 2>/dev/null || echo "0")
if [ "$score" -gt 0 ] 2>/dev/null; then
  ok "score computed (${score})"
else
  fail "score is 0 or invalid"
fi

echo ""
echo "=== $PASS OK, $FAIL FAIL ==="
[ "$FAIL" -eq 0 ]
