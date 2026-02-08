# Harvest Moon 64: Recompiled (WIP)

Work-in-progress static recompilation project for Harvest Moon 64.

This repository is currently based on the Mario Kart 64 recompilation scaffold and is still being converted and cleaned up.

This repo does not contain ROMs, ELFs, or extracted game assets. You must provide your own legally obtained copy of the game.

## Attribution / Credits

- Scaffold / upstream reference: [sonicdcer/MarioKart64Recomp](https://github.com/sonicdcer/MarioKart64Recomp) and its contributors.
- Runtime/tooling: N64: Recompiled modern runtime + toolchain (submodule `lib/N64ModernRuntime` and `N64Recomp/` in this repo).
- Rendering: RT64 (submodule).
- UI: RmlUi (submodule).
- Licensing: see `COPYING` and the license files in submodules.

Note: GitHub's "Contributors" list may show upstream contributors due to the scaffold/history this repo is based on. That is expected and intentional attribution.

## Project Goal

One of the goals of this repo is to explore setting up and iterating on N64 recompilation projects with the help of AI:

- Quickly compare against reference recomp projects and reuse proven patterns.
- Add targeted instrumentation (logs/trace/overlays) to debug black screens, hangs, and scheduler issues without guessing.

## Current State

- Boots with video and audio.
- Main blocker (not playable yet):
  - Visible framebuffer flickering (sync issue).
  - Controller input not working (NuSystem scheduler/input path still missing).

## Quick Start (macOS)

1. Clone with submodules:
   - `git clone --recurse-submodules https://github.com/ai-tdd-labs/harvest-moon-64-recompiled.git`
2. Provide your local ROM/ELF (local-only; do not commit them):
   - `roms/baserom.us.z64`
   - `roms/hm64.elf`
3. Generate recompiled code:
   - `../N64Recomp/build/N64Recomp hm64.us.toml`
4. Configure and build:
   - `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release`
   - `cmake --build build --target HarvestMoon64Recompiled -j$(sysctl -n hw.ncpu)`
5. Run:
   - `./build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled`

## Notes

- App/binary target name: `HarvestMoon64Recompiled`.
- For more build details, see `BUILDING.md`.
