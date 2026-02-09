#include <cmath>
#include <cinttypes>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <array>
#include <sstream>
#include <string>

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

static uint64_t fnv1a64_rdram_unswapped_stride(uint8_t* rdram, uint32_t phys_addr, size_t len, size_t step) {
    uint64_t h = 1469598103934665603ull;
    if (step == 0) {
        step = 1;
    }
    for (size_t i = 0; i < len; i += step) {
        uint8_t b = rdram[(phys_addr + (uint32_t)i) ^ 3u];
        h = fnv1a64_update(h, b);
    }
    return h;
}

static inline bool hm64_truthy(const char* name) {
    return recomp_env_truthy(name) != 0;
}

static inline int hm64_env_int(const char* name, int def) {
    const char* v = getenv(name);
    if (v == NULL || *v == '\0') {
        return def;
    }
    return atoi(v);
}

static inline const char* hm64_env_str(const char* name, const char* def) {
    const char* v = getenv(name);
    if (v == NULL || *v == '\0') {
        return def;
    }
    return v;
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

static inline uint8_t expand_5_to_8(uint8_t v) {
    // 0..31 -> 0..255
    return (uint8_t)((v << 3) | (v >> 2));
}

static inline uint16_t read_be16_unswapped(uint8_t* rdram, uint32_t phys_addr) {
    // RDRAM is byte-swapped by the runtime; undo it per-byte.
    uint8_t hi = rdram[phys_addr ^ 3u];
    uint8_t lo = rdram[(phys_addr + 1u) ^ 3u];
    return (uint16_t)((hi << 8) | lo);
}

static void hm64_dump_fb_ppm(uint8_t* rdram, uint32_t fb_phys, uint64_t seq) {
    // Default is N64 320x240 RGBA5551.
    const int w = hm64_env_int("HM64_FB_DUMP_W", 320);
    const int h = hm64_env_int("HM64_FB_DUMP_H", 240);
    if (w <= 0 || h <= 0) {
        return;
    }

    const uint32_t bytes = (uint32_t)w * (uint32_t)h * 2u;
    if (fb_phys + bytes > 0x00800000u) {
        fprintf(stderr, "[hm64][fbdump] #%llu fb_phys=0x%06X size=0x%X OUT_OF_RANGE\n",
            (unsigned long long)seq, (unsigned)fb_phys, (unsigned)bytes);
        return;
    }

    const char* dir = hm64_env_str("HM64_FB_DUMP_DIR", "tmp/fb_dump");
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);

    std::ostringstream path;
    path << dir << "/fb_" << std::setw(6) << std::setfill('0') << seq
         << "_phys_" << std::hex << std::uppercase << std::setw(6) << std::setfill('0') << fb_phys
         << ".ppm";

    std::ofstream out(path.str(), std::ios::binary);
    if (!out.good()) {
        fprintf(stderr, "[hm64][fbdump] #%llu open_failed path=%s\n",
            (unsigned long long)seq, path.str().c_str());
        return;
    }

    out << "P6\n" << w << " " << h << "\n255\n";
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            const uint32_t off = ((uint32_t)y * (uint32_t)w + (uint32_t)x) * 2u;
            uint16_t px = read_be16_unswapped(rdram, fb_phys + off);
            uint8_t r5 = (uint8_t)((px >> 11) & 0x1Fu);
            uint8_t g5 = (uint8_t)((px >> 6) & 0x1Fu);
            uint8_t b5 = (uint8_t)((px >> 1) & 0x1Fu);
            uint8_t rgb[3] = { expand_5_to_8(r5), expand_5_to_8(g5), expand_5_to_8(b5) };
            out.write((const char*)rgb, 3);
        }
    }

    fprintf(stderr, "[hm64][fbdump] #%llu wrote %s\n", (unsigned long long)seq, path.str().c_str());
}

extern "C" void recomp_vi_observe_tick(uint8_t* rdram, recomp_context* ctx) {
    if (!hm64_truthy("HM64_VI_OBS_LOG") && !hm64_truthy("HM64_VI_OBS_DUMP")) {
        return;
    }

    static uint64_t seq = 0;
    const uint64_t n = ++seq;

    const uint32_t cur = (uint32_t)osViGetCurrentFramebuffer();
    const uint32_t next = (uint32_t)osViGetNextFramebuffer();

    uint32_t cur_phys = 0, next_phys = 0;
    const bool cur_ok = n64_to_phys(cur, &cur_phys);
    const bool next_ok = n64_to_phys(next, &next_phys);

    if (hm64_truthy("HM64_VI_OBS_LOG")) {
        fprintf(stderr, "[hm64][viobs] #%llu cur=0x%08X(%s%06X) next=0x%08X(%s%06X)\n",
            (unsigned long long)n,
            (unsigned)cur, cur_ok ? "phys=0x" : "phys=INVALID:", (unsigned)cur_phys,
            (unsigned)next, next_ok ? "phys=0x" : "phys=INVALID:", (unsigned)next_phys);
    }

    if (hm64_truthy("HM64_VI_OBS_DUMP") && cur_ok) {
        const int after = hm64_env_int("HM64_VI_OBS_DUMP_AFTER", 0);
        const int every = hm64_env_int("HM64_VI_OBS_DUMP_EVERY", 30);
        const int max = hm64_env_int("HM64_VI_OBS_DUMP_MAX", 10);
        static int dumped = 0;
        if ((int)n >= after && every > 0 && (((int)n - after) % every == 0) && dumped < max) {
            const char* dir = hm64_env_str("HM64_VI_OBS_DUMP_DIR", "tmp/vi_fb_dump");
            setenv("HM64_FB_DUMP_DIR", dir, 1);
            hm64_dump_fb_ppm(rdram, cur_phys, n);
            dumped++;
        }
    }
}

extern "C" void recomp_fb_hash_tick(uint8_t* rdram, recomp_context* ctx) {
    static uint64_t seq = 0;
    const uint64_t n = ++seq;

    const uint32_t fb_addr = (uint32_t)ctx->r4;
    uint32_t fb_phys = 0;
    if (!n64_to_phys(fb_addr, &fb_phys)) {
        fprintf(stderr, "[hm64][fbhash] #%llu fb=0x%08X phys=INVALID\n",
            (unsigned long long)n, (unsigned)fb_addr);
        return;
    }

    // Track the set of framebuffers the game cycles through (usually 2 or 3).
    // This lets us dump all buffers per swap, which is useful to detect
    // "swap is showing an old/other buffer" vs "the active render target flickers".
    static std::array<uint32_t, 3> seen_phys = { 0, 0, 0 };
    static int seen_count = 0;
    auto remember_fb = [&](uint32_t p) {
        for (int i = 0; i < seen_count; i++) {
            if (seen_phys[i] == p) {
                return;
            }
        }
        if (seen_count < (int)seen_phys.size()) {
            seen_phys[seen_count++] = p;
        }
    };
    remember_fb(fb_phys);

    // Optional: track whether the game updates every framebuffer it cycles through.
    // If it swaps among N buffers but only renders into 1, the other buffers will be stale and cause flicker.
    if (hm64_truthy("HM64_FB_SET_LOG")) {
        constexpr uint32_t fb_size = 0x00025800u; // 320*240*2
        constexpr uint32_t rdram_size = 0x00800000u;
        // Use a cheap strided hash by default; full hash is available but more expensive.
        const int stride = hm64_env_int("HM64_FB_SET_STRIDE", 16);
        const bool only_changed = hm64_truthy("HM64_FB_SET_ONLY_CHANGED");

        static std::array<uint64_t, 3> last_hash = { 0, 0, 0 };
        static std::array<uint64_t, 3> last_seen_seq = { 0, 0, 0 };
        for (int i = 0; i < seen_count; i++) {
            const uint32_t p = seen_phys[i];
            if (p + fb_size > rdram_size) {
                continue;
            }
            const uint64_t h = fnv1a64_rdram_unswapped_stride(rdram, p, fb_size, (size_t)stride);
            const bool changed = (last_seen_seq[i] != 0) && (last_hash[i] != h);
            if (!only_changed || changed || last_seen_seq[i] == 0) {
                fprintf(stderr, "[hm64][fbset] #%llu idx=%d phys=0x%06X hash=%016" PRIX64 "%s\n",
                    (unsigned long long)n, i, (unsigned)p, h, changed ? " CHANGED" : "");
            }
            last_hash[i] = h;
            last_seen_seq[i] = n;
        }
    }

    // Optional framebuffer dump for ground-truthing "flicker":
    // If consecutive dumps differ, the flicker is in framebuffer content.
    // If dumps are stable but the screen flickers, it's in present/VI/RT64.
    if (hm64_truthy("HM64_FB_DUMP")) {
        const int after = hm64_env_int("HM64_FB_DUMP_AFTER", 0);
        const int every = hm64_env_int("HM64_FB_DUMP_EVERY", 1);
        const int max = hm64_env_int("HM64_FB_DUMP_MAX", 10);
        static int dumped = 0;
        if ((int)n >= after && (every > 0) && (((int)n - after) % every == 0) && dumped < max) {
            const bool dump_all = hm64_truthy("HM64_FB_DUMP_ALL") && seen_count > 0;
            if (!dump_all) {
                hm64_dump_fb_ppm(rdram, fb_phys, n);
            } else {
                for (int i = 0; i < seen_count; i++) {
                    hm64_dump_fb_ppm(rdram, seen_phys[i], n);
                }
            }
            dumped++;
        }
    }

    if (!hm64_truthy("HM64_FB_HASH_LOG")) {
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
