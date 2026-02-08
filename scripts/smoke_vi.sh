#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXE="$ROOT/build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled"
OUT_DIR="$ROOT/tmp"
OUT="$OUT_DIR/vi_smoke.out"

mkdir -p "$OUT_DIR"

if [[ ! -x "$EXE" ]]; then
  echo "missing exe: $EXE" >&2
  exit 2
fi

echo "[smoke] running 20s with VI+SWAP logging -> $OUT" >&2
rm -f "$OUT"

HM64_VI_LOG=1 HM64_SWAP_LOG=1 "$EXE" >"$OUT" 2>&1 &
PID=$!

sleep 20
kill "$PID" 2>/dev/null || true
sleep 1

SWAPS="$(rg -c "\\[hm64\\]\\[swap\\]" "$OUT" || true)"
BLACK1="$(rg -c "osViBlack active=1" "$OUT" || true)"
BLACK0="$(rg -c "osViBlack active=0" "$OUT" || true)"

echo "[smoke] swaps=$SWAPS vi_black_1=$BLACK1 vi_black_0=$BLACK0" >&2

# "Video works" definition: must see at least one unblack.
if [[ "$BLACK0" -lt 1 ]]; then
  echo "[smoke] FAIL: never saw osViBlack active=0 (likely black screen)" >&2
  exit 1
fi

if [[ "$SWAPS" -lt 1 ]]; then
  echo "[smoke] FAIL: never saw swap logs" >&2
  exit 1
fi

echo "[smoke] PASS" >&2

