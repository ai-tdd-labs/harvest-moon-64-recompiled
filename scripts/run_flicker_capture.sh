#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

APP="./build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled"
RUN_LOG="${RUN_LOG:-/tmp/hm64_flicker_capture.log}"
SECONDS_TO_RUN="${SECONDS_TO_RUN:-12}"

rm -f "$RUN_LOG"

echo "APP=$APP" | tee -a "$RUN_LOG"
echo "RUN_LOG=$RUN_LOG" | tee -a "$RUN_LOG"
echo "SECONDS_TO_RUN=$SECONDS_TO_RUN" | tee -a "$RUN_LOG"

echo "--- starting" | tee -a "$RUN_LOG"
HM64_SWAP_LOG=1 \
RECOMP_TRACE_LOG="" \
RECOMP_TRACE_STDERR=0 \
"$APP" >>"$RUN_LOG" 2>&1 &
pid=$!
echo "pid=$pid" | tee -a "$RUN_LOG"

sleep "$SECONDS_TO_RUN" || true
kill "$pid" 2>/dev/null || true
sleep 1 || true
kill -9 "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true

echo "--- swap lines" | tee -a "$RUN_LOG"
rg "^\\[hm64\\]\\[swap\\]" "$RUN_LOG" | tail -n 200 | tee -a "$RUN_LOG" || true

echo "--- done" | tee -a "$RUN_LOG"
