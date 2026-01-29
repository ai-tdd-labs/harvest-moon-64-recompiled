// Minimal patch for HM64 Recompiled
#include "patches.h"

// RT64 Extended GBI command constants (from rt64_extended_gbi.h)
// For F3DEX2 GBI
#define RT64_HOOK_OPCODE         0xE0
#define RT64_HOOK_MAGIC_NUMBER   0x525464
#define RT64_HOOK_OP_ENABLE      0x1
#define RT64_EXTENDED_OPCODE     0x64
#define G_EX_SETREFRESHRATE_V1   0x000009
#define G_EX_SETRDRAMEXTENDED_V1 0x00002C

// GBI command type (8 bytes per command)
typedef struct {
    u32 word0;
    u32 word1;
} Gfx;

// ============================================================
// External function declarations (must be BEFORE any patches!)
// ============================================================

// Yield functions from N64ModernRuntime
extern void yield_self_1ms(void);
extern void yield_self(void);

// VI framebuffer functions for synchronization
// These are critical to prevent white flickering!
// Reference: Goemon64Recomp/patches/keep/sched.c line 406
extern void* osViGetCurrentFramebuffer_recomp(void);
extern void* osViGetNextFramebuffer_recomp(void);
#define osViGetCurrentFramebuffer osViGetCurrentFramebuffer_recomp
#define osViGetNextFramebuffer osViGetNextFramebuffer_recomp

// VI black control from N64ModernRuntime
// osViBlack_recomp is defined in syms.ld -> 0x8F0000EC
extern void osViBlack_recomp(u8 active);
#define osViBlack osViBlack_recomp

// ============================================================
// Patches
// ============================================================

// Dummy export to ensure patches.bin is not empty
RECOMP_EXPORT void hm64_patch_init(void) {
    // Placeholder - add HM64 patches here later
}

// @recomp Enable RT64 extended GBI mode and set refresh rate
// This is critical for proper frame timing and prevents flickering
// Reference: MarioKart64Recomp/patches/gfx_config.c, Goemon64Recomp/patches/main.c
RECOMP_PATCH Gfx* initRcp(Gfx* displayList) {
    Gfx* dl = displayList;

    // TODO: Add framebuffer sync check via TOML hook instead
    // The sync check (osViGetCurrentFramebuffer != osViGetNextFramebuffer)
    // causes compilation errors with N64Recomp. Need different approach.
    // See: Goemon64Recomp/patches/keep/sched.c line 406

    // gEXEnable - Enable RT64 extended GBI mode
    // Command: (RT64_HOOK_OPCODE << 24) | RT64_HOOK_MAGIC_NUMBER, (RT64_HOOK_OP_ENABLE << 28) | RT64_EXTENDED_OPCODE
    dl->word0 = (RT64_HOOK_OPCODE << 24) | RT64_HOOK_MAGIC_NUMBER;  // 0xE0525464
    dl->word1 = (RT64_HOOK_OP_ENABLE << 28) | RT64_EXTENDED_OPCODE; // 0x10000064
    dl++;

    // gEXSetRDRAMExtended(1) - Enable extended RDRAM for larger display lists
    // Command: (RT64_EXTENDED_OPCODE << 24) | G_EX_SETRDRAMEXTENDED_V1, 1
    dl->word0 = (RT64_EXTENDED_OPCODE << 24) | G_EX_SETRDRAMEXTENDED_V1; // 0x6400002C
    dl->word1 = 1;
    dl++;

    // gEXSetRefreshRate(60) - Set target 60 FPS refresh rate
    // HM64 runs at 60 FPS (unlike MK64 which uses 30 for 2-player)
    // Command: (RT64_EXTENDED_OPCODE << 24) | G_EX_SETREFRESHRATE_V1, 60
    dl->word0 = (RT64_EXTENDED_OPCODE << 24) | G_EX_SETREFRESHRATE_V1; // 0x64000009
    dl->word1 = 60;  // 60 FPS
    dl++;

    // Original initRcp code: gSPLoadGeometryMode(0)
    // 0xDB06xxxx = G_LOADGEOMETRYMODE
    dl->word0 = 0xDB060000;
    dl->word1 = 0x00000000;
    dl++;

    // Original initRcp code: gSPDisplayList(0x80112A38)
    // 0xDE00xxxx = G_DL (call display list)
    dl->word0 = 0xDE000000;
    dl->word1 = 0x00112A38;  // Segment address for RSP init DL
    dl++;

    // Original initRcp code: gSPDisplayList(0x80112A10)
    dl->word0 = 0xDE000000;
    dl->word1 = 0x00112A10;  // Segment address for another init DL
    dl++;

    return dl;
}

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
