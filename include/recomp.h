#pragma once

// Project-local wrapper to provide legacy typedefs expected by some generated code.
// The upstream header lives in lib/N64ModernRuntime/N64Recomp/include/recomp.h.
#include_next "recomp.h"

#ifndef __UINT_TYPEDEF_DEFINED__
#define __UINT_TYPEDEF_DEFINED__
typedef unsigned int uint;
#endif

// Utility for TOML hooks: log pointers/state without touching generated headers.
#ifdef __cplusplus
extern "C" {
#endif
void recomp_debug_log_ptrs(const char* tag, uint8_t* rdram, recomp_context* ctx);

// Debug hooks used from hm64.us.toml patches. Keep these declarations here so
// the generated RecompiledFuncs sources can call into the native runtime.
void recomp_fb_hash_tick(uint8_t* rdram, recomp_context* ctx);
void recomp_vi_observe_tick(uint8_t* rdram, recomp_context* ctx);
#ifdef __cplusplus
}
#endif
