// Minimal patch for HM64 Recompiled
#include "patches.h"

// Dummy export to ensure patches.bin is not empty
RECOMP_EXPORT void hm64_patch_init(void) {
    // Placeholder - add HM64 patches here later
}

// Extern declaration for yield function from N64ModernRuntime
extern void yield_self_1ms(void);
static volatile u32 nuGfxTaskAllEndWait_debug_counter = 0;

// NOTE:
// Do not patch/override nuGfxTaskAllEndWait here.
// HM64 relies on its semantics (wait until nuGfxTaskSpool becomes 0). We implement a semantic-preserving
// yield-wait via a TOML hook in `hm64.us.toml` so the graphics thread can run without turning this into
// a no-op (which can cause flicker/tearing by breaking NuSystem's frame pacing).

// Extern declaration for VI black control from N64ModernRuntime
// osViBlack_recomp is defined in syms.ld -> 0x8F0000EC
extern void osViBlack_recomp(u8 active);
#define osViBlack osViBlack_recomp

// @recomp Replace blocking 60-VBlank wait with yield loop
// Original waits for VBlank interrupt to set bit 2, which never fires in recomp
RECOMP_PATCH void func_80026284(void) {
    // Wait ~1 second (60 frames)
    for (int i = 0; i < 60; i++) {
        yield_self_1ms();
    }

    // Set engineStateFlags bit 2 to indicate startup complete
    // Address: 0x80160000 + (-0x6B1C) = 0x801594E4
    volatile u16* engineStateFlags = (volatile u16*)0x801594E4;
    *engineStateFlags |= 0x2;
}

// NuSystem display flag address (from decomp: nuGfxDisplay = 0x80189130)
#define NU_GFX_DISPLAY_ON 1

// @recomp Fix black screen by directly calling osViBlack(FALSE)
// Original NuSystem relies on nuGfxTaskMgr to call osViBlack(FALSE) when
// NU_SC_SWAPBUFFER_MSG is received, but the recomp scheduler doesn't send this.
// This patch calls osViBlack(FALSE) directly when display is enabled.
RECOMP_PATCH void nuGfxDisplayOn(void) {
    // Set the original display flag
    volatile u32* nuGfxDisplay = (volatile u32*)0x80189130;
    *nuGfxDisplay = NU_GFX_DISPLAY_ON;

    // @recomp: Directly disable VI black overlay
    // This is what nuGfxTaskMgr would normally do on SWAPBUFFER_MSG
    osViBlack(0);  // FALSE = disable black overlay = show display
}
