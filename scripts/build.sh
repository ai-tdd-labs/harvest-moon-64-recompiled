#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Build the current macOS app target (name comes from the mk64 base scaffold).
cmake --build build --target MarioKart64Recompiled -j"$(sysctl -n hw.ncpu)"

