# Harvest Moon 64: Recompiled (WIP)

Work-in-progress static recompilation project for Harvest Moon 64.

This repository is currently based on the `MarioKart64Recomp` scaffold and is still being converted and cleaned up.

This repo does not contain ROMs, ELFs, or extracted game assets. You must provide your own legally obtained copy of the game.

## Current State

- Boots with video and audio.
- Main blocker (not playable yet):
  - Visible framebuffer flickering (sync issue).
  - Controller input not working (NuSystem scheduler/input path still missing).
- Note: the app/binary target name is still inherited from the MK64 scaffold (`MarioKart64Recompiled`).

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
   - `cmake --build build --target MarioKart64Recompiled -j$(sysctl -n hw.ncpu)`
5. Run:
   - `./build/MarioKart64Recompiled.app/Contents/MacOS/MarioKart64Recompiled`

## Notes

- The app/binary target name is still inherited from the MK64 scaffold (`MarioKart64Recompiled`). Renaming will happen once the HM64 conversion stabilizes.
- For more build details, see `BUILDING.md`.

## Credits / Upstream

- Built on the N64: Recompiled modern runtime (submodule `lib/N64ModernRuntime`).
- Rendering uses RT64, UI uses RmlUi (submodules).
