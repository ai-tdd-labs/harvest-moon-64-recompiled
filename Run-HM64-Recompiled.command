#!/bin/bash
set -euo pipefail

# Double-clickable launcher for macOS.
# Opens the repo in Finder, then runs the built app (no rebuild).

ROOT="$(cd "$(dirname "$0")" && pwd)"

open "$ROOT"

APP="$ROOT/build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled"
if [[ ! -x "$APP" ]]; then
  osascript -e 'display dialog "Build not found. Run: cmake --build build --target HarvestMoon64Recompiled" buttons {"OK"} default button "OK" with title "Harvest Moon 64: Recompiled"'
  exit 1
fi

# Keep flicker mitigation on by default; users can override by exporting HM64_DISABLE_INSTANT_PRESENT=0.
export HM64_DISABLE_INSTANT_PRESENT="${HM64_DISABLE_INSTANT_PRESENT:-1}"
# Autostart is opt-in; enable with RECOMP_AUTOSTART=1 (and optionally RECOMP_AUTOSTART_DELAY_MS).
export RECOMP_AUTOSTART="${RECOMP_AUTOSTART:-0}"

exec "$APP"
