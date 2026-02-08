#pragma once

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef RECOMP_TRACE
#define RECOMP_TRACE 0
#endif

static inline int recomp_env_truthy(const char* env_name) {
    const char* v = getenv(env_name);
    if (v == NULL) {
        return 0;
    }
    // Accept common truthy values.
    return (v[0] == '1') || (v[0] == 'y') || (v[0] == 'Y') || (v[0] == 't') || (v[0] == 'T');
}

static inline FILE* recomp_trace_log_file() {
    static FILE* file = NULL;
    static int initialized = 0;

    if (!initialized) {
        // Only log to a file when explicitly requested. This avoids filling disks
        // and keeps normal runs quiet.
        const char* path = getenv("RECOMP_TRACE_LOG");
        if (path != NULL && *path != '\0') {
            file = fopen(path, "a");
        }
        if (file != NULL) {
            setvbuf(file, NULL, _IOLBF, 0);
        }
        initialized = 1;
    }

    return file;
}

static inline void recomp_trace_entry(const char* func_name) {
    FILE* file = recomp_trace_log_file();
    if (file != NULL) {
        fprintf(file, "[trace] -> %s\n", func_name);
    }
    if (recomp_env_truthy("RECOMP_TRACE_STDERR")) {
        fprintf(stderr, "[trace] -> %s\n", func_name);
    }
}

static inline void recomp_trace_return(const char* func_name) {
    FILE* file = recomp_trace_log_file();
    if (file != NULL) {
        fprintf(file, "[trace] <- %s\n", func_name);
    }
    if (recomp_env_truthy("RECOMP_TRACE_STDERR")) {
        fprintf(stderr, "[trace] <- %s\n", func_name);
    }
}

#if RECOMP_TRACE
#define TRACE_ENTRY() recomp_trace_entry(__func__);
#define TRACE_RETURN() recomp_trace_return(__func__);
#else
#define TRACE_ENTRY() ((void)0);
#define TRACE_RETURN() ((void)0);
#endif

// Minimal, targeted logging for framebuffer swap debugging.
static inline void hm64_swap_log(const char* tag, uint32_t a0, uint32_t fb) {
    if (!recomp_env_truthy("HM64_SWAP_LOG")) {
        return;
    }

    static uint64_t seq = 0;
    seq++;
    fprintf(stderr, "[hm64][swap] #%llu %s a0=0x%08X fb=0x%08X\n",
        (unsigned long long)seq, tag, (unsigned)a0, (unsigned)fb);
}
