TARGET = patches.elf

# Use Homebrew LLVM for MIPS cross-compilation
CC      := /opt/homebrew/opt/llvm/bin/clang
LD      := /opt/homebrew/bin/ld.lld

CFLAGS   := -target mips -mips2 -mabi=32 -O2 -G0 -mno-abicalls -mno-odd-spreg -mno-check-zero-division \
			-fomit-frame-pointer -ffast-math -fno-unsafe-math-optimizations -fno-builtin-memset \
			-Wall -Wextra -Wno-incompatible-library-redeclaration -Wno-unused-parameter -Wno-unknown-pragmas -Wno-unused-variable -Wno-unused-but-set-variable -Wno-missing-braces -Wno-unsupported-floating-point-opt -Wno-switch

# Include paths - using hm64-decomp headers
CPPFLAGS := -nostdinc -DTARGET_N64 -DF3DEX_GBI -D_LANGUAGE_C -DMIPS \
			-I ../lib/mk64/include \
			-I ../lib/mk64/include/PR \
			-I ../lib/mk64/include/libc \
			-I ../lib/rt64/include

LDFLAGS  := -nostdlib -T patches.ld -T syms.ld -Map patches.map --unresolved-symbols=ignore-all --emit-relocs

# Only compile HM64-specific patches (exclude MK64 patchset).
C_SRCS := stub.c
C_OBJS := $(C_SRCS:.c=.o)
C_DEPS := $(C_SRCS:.c=.d)

$(TARGET): $(C_OBJS) patches.ld syms.ld
	$(LD) $(C_OBJS) $(LDFLAGS) -o $@

$(C_OBJS): %.o : %.c
	$(CC) $(CFLAGS) $(CPPFLAGS) $< -MMD -MF $(@:.o=.d) -c -o $@

clean:
	rm -rf $(C_OBJS) $(TARGET) $(C_DEPS) patches.map patches.bin

-include $(C_DEPS)

.PHONY: clean
