#pragma once

#include <stdio.h>
#include <stdlib.h>

#ifndef RECOMP_TRACE
#define RECOMP_TRACE 1
#endif

static inline FILE* recomp_trace_log_file() {
    static FILE* file = NULL;
    static int initialized = 0;

    if (!initialized) {
        const char* path = getenv("RECOMP_TRACE_LOG");
        if (path == NULL || *path == '\0') {
            path = "/tmp/hm64_trace.log";
        }
        file = fopen(path, "a");
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
    fprintf(stderr, "[trace] -> %s\n", func_name);
}

static inline void recomp_trace_return(const char* func_name) {
    FILE* file = recomp_trace_log_file();
    if (file != NULL) {
        fprintf(file, "[trace] <- %s\n", func_name);
    }
    fprintf(stderr, "[trace] <- %s\n", func_name);
}

#if RECOMP_TRACE
#define TRACE_ENTRY() recomp_trace_entry(__func__);
#define TRACE_RETURN() recomp_trace_return(__func__);
#else
#define TRACE_ENTRY() ((void)0);
#define TRACE_RETURN() ((void)0);
#endif
