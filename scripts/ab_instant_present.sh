#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled"

SECONDS_TO_RUN="${SECONDS_TO_RUN:-12}"
LOG_NORMAL="${LOG_NORMAL:-/tmp/hm64_ab_normal.log}"
LOG_NOEARLY="${LOG_NOEARLY:-/tmp/hm64_ab_noearly.log}"

if [[ ! -x "$APP" ]]; then
  echo "missing app: $APP" >&2
  exit 2
fi

run_case() {
  local label="$1"
  local log="$2"
  shift 2

  rm -f "$log"
  echo "case=$label" | tee -a "$log"
  echo "seconds=$SECONDS_TO_RUN" | tee -a "$log"
  echo "cmd=$*" | tee -a "$log"

  "$@" >>"$log" 2>&1 &
  local pid=$!
  echo "pid=$pid" | tee -a "$log"
  sleep "$SECONDS_TO_RUN" || true
  kill "$pid" 2>/dev/null || true
  sleep 1 || true
  kill -9 "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  echo "done=1" | tee -a "$log"
}

echo "[ab] normal -> $LOG_NORMAL" >&2
run_case "normal" "$LOG_NORMAL" env RECOMP_TRACE_STDERR=0 "$APP"

echo "[ab] disable_instant_present -> $LOG_NOEARLY" >&2
run_case "disable_instant_present" "$LOG_NOEARLY" env HM64_DISABLE_INSTANT_PRESENT=1 RECOMP_TRACE_STDERR=0 "$APP"

echo "[ab] logs written:" >&2
echo "  $LOG_NORMAL" >&2
echo "  $LOG_NOEARLY" >&2
