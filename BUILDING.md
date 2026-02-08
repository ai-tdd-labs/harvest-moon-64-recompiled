# Building Guide (WIP)

This project is a work-in-progress and is still being converted from the `MarioKart64Recomp` scaffold to Harvest Moon 64.

Note: `MarioKart64Recomp` is used as the build/runtime scaffold. Game-specific code generation is driven by `hm64.us.toml`.

This repository does not include ROMs, ELFs, or extracted game assets.

## 1. Clone

This project uses git submodules:

```bash
git clone --recurse-submodules https://github.com/ai-tdd-labs/harvest-moon-64-recompiled.git
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

If submodule init fails with an SSH error for `lib/mk64/tools/asm-processor`, you can force HTTPS:

```bash
cd lib/mk64
git config submodule.tools/asm-processor.url https://github.com/simonlindholm/asm-processor.git
git submodule update --init --recursive
cd ../..
```

## 2. Dependencies

macOS (Apple Silicon) builds are supported using CMake + Ninja. You will need:

- `cmake`
- `ninja`
- `llvm` (for the `patches/` MIPS build)
- `sdl2`

Exact package names depend on your setup (Homebrew on macOS).

## 3. Provide Local ROM/ELF (Not Committed)

Place the following local-only files in `roms/`:

- `roms/baserom.us.z64`
- `roms/hm64.elf`

## 4. Generate Recompiled Code

Run N64Recomp using the HM64 config:

```bash
../N64Recomp/build/N64Recomp hm64.us.toml
```

If you modify audio microcode in `rsp/`, rebuild it with:

```bash
../N64Recomp/build/RSPRecomp aspMain.us.toml
```

## 5. Build (macOS)

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --target HarvestMoon64Recompiled -j$(sysctl -n hw.ncpu)
```

## 6. Run

```bash
./build/HarvestMoon64Recompiled.app/Contents/MacOS/HarvestMoon64Recompiled
```
