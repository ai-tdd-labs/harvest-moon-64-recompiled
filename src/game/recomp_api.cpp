#include <cmath>
#include <cinttypes>

#include "recomp.h"
#include "librecomp/overlays.hpp"
#include "zelda_config.h"
#include "recomp_input.h"
#include "recomp_ui.h"
#include "trace.h"
#include "zelda_render.h"
#include "zelda_sound.h"
#include "librecomp/helpers.hpp"
// #include "../patches/input.h"
// #include "../patches/graphics.h"
// #include "../patches/sound.h"
#include "ultramodern/ultramodern.hpp"
#include "ultramodern/config.hpp"

static inline uint64_t fnv1a64_update(uint64_t h, uint8_t b) {
    h ^= (uint64_t)b;
    return h * 1099511628211ull;
}

static uint64_t fnv1a64_rdram_unswapped(uint8_t* rdram, uint32_t phys_addr, size_t len) {
    uint64_t h = 1469598103934665603ull;
    for (size_t i = 0; i < len; i++) {
        // RDRAM is byte-swapped in the runtime; undo it for stable comparisons.
        uint8_t b = rdram[(phys_addr + (uint32_t)i) ^ 3u];
        h = fnv1a64_update(h, b);
    }
    return h;
}

static inline bool hm64_truthy(const char* name) {
    return recomp_env_truthy(name) != 0;
}

static inline bool n64_to_phys(uint32_t n64_addr, uint32_t* phys_out) {
    // Accept both raw physical and KSEG0/KSEG1 virtual addresses.
    uint32_t phys = n64_addr;
    if (n64_addr >= 0x80000000u) {
        phys = n64_addr & 0x00FFFFFFu;
    }
    // HM64 uses 8MB RDRAM.
    if (phys >= 0x00800000u) {
        return false;
    }
    *phys_out = phys;
    return true;
}

extern "C" void recomp_fb_hash_tick(uint8_t* rdram, recomp_context* ctx) {
    if (!hm64_truthy("HM64_FB_HASH_LOG")) {
        return;
    }

    static uint64_t seq = 0;
    const uint64_t n = ++seq;

    const uint32_t fb_addr = (uint32_t)ctx->r4;
    uint32_t fb_phys = 0;
    if (!n64_to_phys(fb_addr, &fb_phys)) {
        fprintf(stderr, "[hm64][fbhash] #%llu fb=0x%08X phys=INVALID\n",
            (unsigned long long)n, (unsigned)fb_addr);
        return;
    }

    // Sample a few stripes within a typical 320x240x16b framebuffer region (0x25800 bytes).
    // If the game uses a different layout, hashes may still be useful (they'll just include adjacent data).
    constexpr uint32_t rdram_size = 0x00800000u;
    constexpr uint32_t fb_guess_size = 0x00025800u;
    constexpr size_t chunk = 4096;
    const uint32_t max_safe = rdram_size - (uint32_t)chunk;

    const uint32_t o0 = fb_phys;
    const uint32_t o1 = (fb_phys + 0x00001000u <= max_safe) ? (fb_phys + 0x00001000u) : fb_phys;
    const uint32_t o2 = (fb_phys + 0x00010000u <= max_safe) ? (fb_phys + 0x00010000u) : fb_phys;
    const uint32_t o3 = (fb_phys + (fb_guess_size > chunk ? (fb_guess_size - (uint32_t)chunk) : 0u) <= max_safe)
        ? (fb_phys + (fb_guess_size - (uint32_t)chunk))
        : fb_phys;

    uint64_t h0 = fnv1a64_rdram_unswapped(rdram, o0, chunk);
    uint64_t h1 = fnv1a64_rdram_unswapped(rdram, o1, chunk);
    uint64_t h2 = fnv1a64_rdram_unswapped(rdram, o2, chunk);
    uint64_t h3 = fnv1a64_rdram_unswapped(rdram, o3, chunk);

    fprintf(stderr,
        "[hm64][fbhash] #%llu fb=0x%08X phys=0x%06X h=%016" PRIX64 ":%016" PRIX64 ":%016" PRIX64 ":%016" PRIX64 "\n",
        (unsigned long long)n, (unsigned)fb_addr, (unsigned)fb_phys, h0, h1, h2, h3);
}

extern "C" void recomp_update_inputs(uint8_t* rdram, recomp_context* ctx) {
    recomp::poll_inputs();
}

extern "C" void recomp_sleep_miliseconds(uint8_t* rdram, recomp_context* ctx) {
    int time = _arg<0, u32>(rdram, ctx);
    ultramodern::sleep_milliseconds(time);
}


extern "C" void rmonPrintf_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Empty
}

extern "C" void __ll_rshift_recomp(uint8_t * rdram, recomp_context * ctx) {
    int64_t a = (ctx->r4 << 32) | ((ctx->r5 << 0) & 0xFFFFFFFFu);
    int64_t b = (ctx->r6 << 32) | ((ctx->r7 << 0) & 0xFFFFFFFFu);
    int64_t ret = a >> b;

    ctx->r2 = (int32_t)(ret >> 32);
    ctx->r3 = (int32_t)(ret >> 0);
}

extern "C" void recomp_puts(uint8_t* rdram, recomp_context* ctx) {
    PTR(char) cur_str = _arg<0, PTR(char)>(rdram, ctx);
    u32 length = _arg<1, u32>(rdram, ctx);

    for (u32 i = 0; i < length; i++) {
        fputc(MEM_B(i, (gpr)cur_str), stdout);
    }
}

extern "C" void recomp_debug_u32(uint8_t* rdram, recomp_context* ctx) {
    u32 tag = _arg<0, u32>(rdram, ctx);
    u32 value = _arg<1, u32>(rdram, ctx);
    FILE* file = recomp_trace_log_file();
    if (file != NULL) {
        fprintf(file, "[patch] tag=0x%08X value=0x%08X\n", tag, value);
    }
    fprintf(stderr, "[patch] tag=0x%08X value=0x%08X\n", tag, value);
}

extern "C" void recomp_debug_log_ptrs(const char* tag, uint8_t* rdram, recomp_context* ctx) {
    FILE* file = recomp_trace_log_file();
    if (file == NULL) {
        return;
    }

    // Keep it simple: pointers only. Avoid dereferencing ctx/rdram to keep this safe even in bad states.
    fprintf(file, "[dbg] %s rdram=%p ctx=%p\n", tag ? tag : "(null)", (void*)rdram, (void*)ctx);
    fflush(file);
}

extern "C" void bzero_recomp(uint8_t* rdram, recomp_context* ctx) {
    u32 addr = _arg<0, u32>(rdram, ctx);
    u32 size = _arg<1, u32>(rdram, ctx);

    if (addr >= 0x80000000 && addr < 0x80800000 && size < 0x800000) {
        uint8_t* ptr = rdram + (addr - 0x80000000);
        for (u32 i = 0; i < size; i++) {
            ptr[i] = 0;
        }
    }
}

extern "C" void recomp_exit(uint8_t* rdram, recomp_context* ctx) {
    ultramodern::quit();
}

extern "C" void recomp_get_gyro_deltas(uint8_t* rdram, recomp_context* ctx) {
    float* x_out = _arg<0, float*>(rdram, ctx);
    float* y_out = _arg<1, float*>(rdram, ctx);

    recomp::get_gyro_deltas(x_out, y_out);
}

extern "C" void recomp_get_mouse_deltas(uint8_t* rdram, recomp_context* ctx) {
    float* x_out = _arg<0, float*>(rdram, ctx);
    float* y_out = _arg<1, float*>(rdram, ctx);

    recomp::get_mouse_deltas(x_out, y_out);
}

extern "C" void recomp_powf(uint8_t* rdram, recomp_context* ctx) {
    float a = _arg<0, float>(rdram, ctx);
    float b = ctx->f14.fl; //_arg<1, float>(rdram, ctx);

    _return(ctx, std::pow(a, b));
}

extern "C" void recomp_get_target_framerate(uint8_t* rdram, recomp_context* ctx) {
    int frame_divisor = _arg<0, u32>(rdram, ctx);

    _return(ctx, ultramodern::get_target_framerate(60 / frame_divisor));
}

extern "C" void recomp_get_window_resolution(uint8_t* rdram, recomp_context* ctx) {
    int width, height;
    recompui::get_window_size(width, height);

    gpr width_out = _arg<0, PTR(u32)>(rdram, ctx);
    gpr height_out = _arg<1, PTR(u32)>(rdram, ctx);

    MEM_W(0, width_out) = (u32) width;
    MEM_W(0, height_out) = (u32) height;
}

extern "C" void recomp_get_aspect_ratio(uint8_t* rdram, recomp_context* ctx) {
    ultramodern::renderer::GraphicsConfig graphics_config = ultramodern::renderer::get_graphics_config();
    float original = _arg<0, float>(rdram, ctx);
    int width, height;
    recompui::get_window_size(width, height);

    switch (graphics_config.ar_option) {
        case ultramodern::renderer::AspectRatio::Original:
        default:
            _return(ctx, original);
            return;
        case ultramodern::renderer::AspectRatio::Expand:
            _return(ctx, std::max(static_cast<float>(width) / height, original));
            return;
    }
}

extern "C" void recomp_get_targeting_mode(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, static_cast<int>(zelda64::get_targeting_mode()));
}

extern "C" void recomp_get_bgm_volume(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, zelda64::get_bgm_volume() / 100.0f);
}

extern "C" void recomp_set_bgm_volume_100(uint8_t* rdram, recomp_context* ctx) {
    zelda64::set_bgm_volume(100);
}

extern "C" void recomp_set_bgm_volume_59(uint8_t* rdram, recomp_context* ctx) {
    zelda64::set_bgm_volume(59);
}

extern "C" void recomp_set_bgm_volume_0(uint8_t* rdram, recomp_context* ctx) {
    zelda64::set_bgm_volume(0);
}

extern "C" void recomp_get_sfx_volume(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, zelda64::get_sfx_volume() / 100.0f);
}

extern "C" void recomp_get_env_volume(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, zelda64::get_env_volume() / 100.0f);
}

extern "C" void recomp_get_low_health_beeps_enabled(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, static_cast<u32>(zelda64::get_low_health_beeps_enabled()));
}

extern "C" void recomp_time_us(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, static_cast<u32>(std::chrono::duration_cast<std::chrono::microseconds>(ultramodern::time_since_start()).count()));
}

extern "C" void recomp_autosave_enabled(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, static_cast<s32>(zelda64::get_autosave_mode() == zelda64::AutosaveMode::On));
}

extern "C" void recomp_load_overlays(uint8_t * rdram, recomp_context * ctx) {
    u32 rom = _arg<0, u32>(rdram, ctx);
    PTR(void) ram = _arg<1, PTR(void)>(rdram, ctx);
    u32 size = _arg<2, u32>(rdram, ctx);

    load_overlays(rom, ram, size);
}

extern "C" void recomp_high_precision_fb_enabled(uint8_t * rdram, recomp_context * ctx) {
    _return(ctx, static_cast<s32>(zelda64::renderer::RT64HighPrecisionFBEnabled()));
}

extern "C" void recomp_get_resolution_scale(uint8_t* rdram, recomp_context* ctx) {
    _return(ctx, ultramodern::get_resolution_scale());
}

extern "C" void recomp_get_inverted_axes(uint8_t* rdram, recomp_context* ctx) {
    s32* x_out = _arg<0, s32*>(rdram, ctx);
    s32* y_out = _arg<1, s32*>(rdram, ctx);

    zelda64::CameraInvertMode mode = zelda64::get_camera_invert_mode();

    *x_out = (mode == zelda64::CameraInvertMode::InvertX || mode == zelda64::CameraInvertMode::InvertBoth);
    *y_out = (mode == zelda64::CameraInvertMode::InvertY || mode == zelda64::CameraInvertMode::InvertBoth);
}

extern "C" void recomp_get_analog_inverted_axes(uint8_t* rdram, recomp_context* ctx) {
    s32* x_out = _arg<0, s32*>(rdram, ctx);
    s32* y_out = _arg<1, s32*>(rdram, ctx);

    zelda64::CameraInvertMode mode = zelda64::get_analog_camera_invert_mode();

    *x_out = (mode == zelda64::CameraInvertMode::InvertX || mode == zelda64::CameraInvertMode::InvertBoth);
    *y_out = (mode == zelda64::CameraInvertMode::InvertY || mode == zelda64::CameraInvertMode::InvertBoth);
}

extern "C" void recomp_analog_cam_enabled(uint8_t* rdram, recomp_context* ctx) {
    _return<s32>(ctx, zelda64::get_analog_cam_mode() == zelda64::AnalogCamMode::On);
}

extern "C" void recomp_get_camera_inputs(uint8_t* rdram, recomp_context* ctx) {
    float* x_out = _arg<0, float*>(rdram, ctx);
    float* y_out = _arg<1, float*>(rdram, ctx);

    // TODO expose this in the menu
    constexpr float radial_deadzone = 0.05f;

    float x, y;

    recomp::get_right_analog(&x, &y);

    float magnitude = sqrtf(x * x + y * y);

    if (magnitude < radial_deadzone) {
        *x_out = 0.0f;
        *y_out = 0.0f;
    }
    else {
        float x_normalized = x / magnitude;
        float y_normalized = y / magnitude;

        *x_out = x_normalized * ((magnitude - radial_deadzone) / (1 - radial_deadzone));
        *y_out = y_normalized * ((magnitude - radial_deadzone) / (1 - radial_deadzone));
    }
}

extern "C" void recomp_set_right_analog_suppressed(uint8_t* rdram, recomp_context* ctx) {
    s32 suppressed = _arg<0, s32>(rdram, ctx);

    recomp::set_right_analog_suppressed(suppressed);
}

// HM64 stub functions - these are referenced by patches but not used yet
extern "C" void recomp_printf(uint8_t* rdram, recomp_context* ctx) {
    // Stub - HM64 doesn't have a recompiled printf, patches can call this
    // For now, just do nothing. Can add actual printf later if needed.
}
