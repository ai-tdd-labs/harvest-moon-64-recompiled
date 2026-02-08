#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Build the current macOS app target.
cmake --build build --target HarvestMoon64Recompiled -j"$(sysctl -n hw.ncpu)"
