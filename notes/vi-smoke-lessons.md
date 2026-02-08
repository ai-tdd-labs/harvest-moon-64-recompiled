# VI Smoke Test Lessons

## Definition of "Video Works"

Do not use `osViSwapBuffer` activity alone as proof that the screen should show an image.

Observed failure mode:
- `osViSwapBuffer` continues to be called (swaps keep happening)
- but `osViBlack(1)` stays asserted and we never see `osViBlack(0)`
- result: black screen even though swaps appear "healthy"

Practical smoke-test rule (after `start_game`):
- Require at least one `osViBlack active=0` log line
- and require ongoing `osViSwapBuffer` logs

Suggested env flags for validation:
- `HM64_VI_LOG=1` to log `osViBlack` / VI mode calls
- `HM64_SWAP_LOG=1` to log swap cadence

## Hook Minimization Notes

- `nuGfxTaskAllEndWait` yield-wait hook is required.
  - Removing it causes init to hang in `nuGfxTaskAllEndWait -> nuGfxInit -> graphicsInit -> initializeEngine`
  - Symptom: `osViBlack` stays asserted and no usable video output

- `func_80026284` yield hook is required to reliably reach VI unblack.
  - Attempted removal (regen + rebuild) caused `scripts/smoke_vi.sh` to FAIL:
    - swaps were missing/unstable
    - `osViBlack active=0` never appeared (VI stayed black)
  - Restoring the hook makes `scripts/smoke_vi.sh` PASS again (unblack observed).
