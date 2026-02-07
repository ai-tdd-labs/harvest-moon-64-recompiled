#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

APP="./build/MarioKart64Recompiled.app/Contents/MacOS/MarioKart64Recompiled"
TRACE_LOG="${RECOMP_TRACE_LOG:-/tmp/hm64_mk64base_trace.log}"
RUN_LOG="${RUN_LOG:-/tmp/hm64_mk64base_run.log}"
SECONDS_TO_RUN="${SECONDS_TO_RUN:-20}"

rm -f "$TRACE_LOG" "$RUN_LOG"

echo "APP=$APP"
echo "TRACE_LOG=$TRACE_LOG"
echo "RUN_LOG=$RUN_LOG"
echo "SECONDS_TO_RUN=$SECONDS_TO_RUN"

RECOMP_TRACE_LOG="$TRACE_LOG" "$APP" >"$RUN_LOG" 2>&1 &
pid=$!
echo "pid=$pid"

sleep "$SECONDS_TO_RUN" || true
kill "$pid" 2>/dev/null || true
sleep 2 || true
kill -9 "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true

echo "--- trace tail"
tail -n 120 "$TRACE_LOG" || true
echo "--- run tail"
tail -n 120 "$RUN_LOG" || true

