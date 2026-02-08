#ifndef __PATCHES_H__
#define __PATCHES_H__

#define RECOMP_EXPORT __attribute__((section(".recomp_export")))
#define RECOMP_PATCH __attribute__((section(".recomp_patch")))
#define RECOMP_FORCE_PATCH __attribute__((section(".recomp_force_patch")))

// Keep patch builds self-contained: only depend on basic N64 types.
// The full MK64 patch header pulls in many decomp headers that we do not ship.
#include "PR/ultratypes.h"
#endif
