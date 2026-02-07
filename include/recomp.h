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
#ifdef __cplusplus
}
#endif
