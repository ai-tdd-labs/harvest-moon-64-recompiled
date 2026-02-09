# Flicker Debugging Notes (Evidence-Based)

This document explains how the "bright areas flicker" issue was debugged and fixed in an evidence-based way.
It is written to be useful both for humans and for LLM-powered agents working on this repo.

## Symptom

- Visible flicker/tearing most noticeable on bright UI/flat colors.

## Ground Rules

- Do not guess. Prefer reference projects and data.
- Separate "framebuffer content is wrong" from "present/scanout is wrong".

## Repro (A/B)

Run the app normally:

```bash
./build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled
```

Run with instant present disabled (expected: stable image on affected setups):

```bash
HM64_DISABLE_INSTANT_PRESENT=1 ./build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled
```

## Evidence Collection

### 1) Verify the game is swapping buffers and VI is un-blackened

We used a minimal definition of "video works":

- At least one `osViBlack active=0` observed
- Ongoing `osViSwapBuffer` activity observed

Script:

```bash
./scripts/smoke_vi.sh
```

Source: `notes/vi-smoke-lessons.md`

### 2) Prove it's not swapping stale framebuffers

We logged hashes for the set of framebuffers the game cycles through (typically 3 in HM64).

Key observation:

- Each framebuffer's content changed in sequence while the swap rotated.
- No swaps to a framebuffer that was "old" relative to the others.

This rules out the common cause: cycling 3 buffers but only rendering into 1.

## Root Cause

The flicker was caused by RT64 "instant present" (PresentEarly) being enabled after `game started`.

- PresentEarly reduces latency.
- On some setups it can present while scanout is in progress, producing visible tearing/flicker.
- This matches the symptom (bright areas show it most) and the A/B result above.

The A/B toggle conclusively showed:

- Flicker present with instant present enabled
- Flicker gone with instant present disabled

## Fix

Two parts:

1) Modern runtime: gate `renderer_context->enable_instant_present()` behind a toggle.
   - Toggle: `HM64_DISABLE_INSTANT_PRESENT=1`
2) HM64 app: default `HM64_DISABLE_INSTANT_PRESENT=1` when not explicitly set.

## Files / References

- Runtime present enable point:
  - `lib/N64ModernRuntime/ultramodern/src/events.cpp`
- HM64 default environment setup:
  - `src/main/main.cpp`
- Smoke test:
  - `scripts/smoke_vi.sh`
- Lessons learned:
  - `notes/vi-smoke-lessons.md`
# NOTE:
# This file lives under `docs/debug/` and would match a common `.gitignore` pattern like `[Dd]ebug/`.
# If you cannot add it, ensure `.gitignore` does not ignore `docs/` (see `.gitignore`).

