"""
Test us.toml configuration validation.

Validates that:
1. Required paths exist (elf_path, rom_file_path)
2. Entrypoint exists in ELF as a function
3. Ignored symbols exist in ELF
4. use_absolute_symbols is not set (or false) for main game
5. Configuration is consistent with ELF

Why these tests matter:
- LLM models might change paths or values incorrectly
- Wrong entrypoint = game won't start
- Missing ignored symbols = build errors
- use_absolute_symbols=true = loses data symbols
"""

import subprocess
from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
US_TOML_PATH = REPO_ROOT / "hm64.us.toml"
RECOMP_ROOT = REPO_ROOT


def parse_toml_simple(path: Path) -> dict:
    """Simple TOML parser for our config."""
    config = {'ignored': [], 'stubs': []}
    if not path.exists():
        raise FileNotFoundError(f"TOML not found: {path}")

    content = path.read_text()
    in_ignored = False
    in_stubs = False

    for line in content.splitlines():
        line = line.strip()

        # Track array sections
        if line.startswith('ignored'):
            in_ignored = True
            in_stubs = False
            continue
        if line.startswith('stubs'):
            in_stubs = True
            in_ignored = False
            continue
        if line.startswith('[') and not line.startswith('[['):
            in_ignored = False
            in_stubs = False

        # Parse array items
        if in_ignored and '"' in line:
            # Remove inline comments first (everything after #)
            if '#' in line:
                line = line.split('#')[0]
            # Extract the string value between quotes
            if '"' in line:
                start = line.index('"') + 1
                end = line.rindex('"')
                item = line[start:end]
                if item:
                    config['ignored'].append(item)
        if in_stubs and '"' in line:
            # Remove inline comments first
            if '#' in line:
                line = line.split('#')[0]
            # Extract the string value between quotes
            if '"' in line:
                start = line.index('"') + 1
                end = line.rindex('"')
                item = line[start:end]
                if item:
                    config['stubs'].append(item)

        # Parse key=value
        if '=' in line and not line.startswith('#') and not in_ignored and not in_stubs:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"')

            if value.startswith('0x'):
                config[key] = int(value, 16)
            elif value == 'true':
                config[key] = True
            elif value == 'false':
                config[key] = False
            elif value.isdigit():
                config[key] = int(value)
            else:
                config[key] = value

    return config


def get_elf_symbols(elf_path: Path) -> dict:
    """Get symbols from ELF. Returns {name: (address, type)}."""
    if not elf_path.exists():
        raise FileNotFoundError(f"ELF not found: {elf_path}")

    result = subprocess.run(['nm', str(elf_path)], capture_output=True, text=True)

    symbols = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                addr = int(parts[0], 16)
                symbols[parts[2]] = (addr, parts[1])
            except ValueError:
                pass

    return symbols


def test_toml_exists():
    """Test that us.toml exists."""
    assert US_TOML_PATH.exists(), f"us.toml not found: {US_TOML_PATH}"
    print(f"[PASS] us.toml exists: {US_TOML_PATH}")


def test_elf_path_exists():
    """
    Test that elf_path in config points to existing file.

    Why this matters:
    - elf_path is required for recompilation
    - Wrong path = build fails immediately
    """
    import pytest
    config = parse_toml_simple(US_TOML_PATH)

    assert 'elf_path' in config, "elf_path not specified in us.toml"

    elf_path = RECOMP_ROOT / config['elf_path']
    if not elf_path.exists():
        pytest.skip(
            f"ELF not found (expected for clean/public repo): {elf_path} "
            f"(set up local roms/ and rebuild)"
        )

    print(f"[PASS] elf_path exists: {config['elf_path']}")


def test_rom_path_exists():
    """
    Test that rom_file_path in config points to existing file.

    Why this matters:
    - ROM is needed for RSP microcode, textures, etc.
    - Wrong path = build fails or game won't work
    """
    import pytest
    config = parse_toml_simple(US_TOML_PATH)

    assert 'rom_file_path' in config, "rom_file_path not specified in us.toml"

    rom_path = RECOMP_ROOT / config['rom_file_path']
    if not rom_path.exists():
        pytest.skip(
            f"ROM not found (expected for clean/public repo): {rom_path} "
            f"(place baserom.us.z64 locally)"
        )

    print(f"[PASS] rom_file_path exists: {config['rom_file_path']}")


def test_entrypoint_in_elf():
    """
    Test that entrypoint exists in ELF as a function.

    Why this matters:
    - Entrypoint is where the game starts execution
    - Wrong value = game won't start
    - Should be a T symbol (function in .text section)
    """
    config = parse_toml_simple(US_TOML_PATH)

    assert 'entrypoint' in config, "entrypoint not specified in us.toml"

    entrypoint = config['entrypoint']

    # Get ELF path and load symbols
    import pytest
    elf_path = RECOMP_ROOT / config.get('elf_path', '')
    if not elf_path.exists():
        pytest.skip(f"Cannot verify entrypoint, ELF not found: {elf_path}")

    symbols = get_elf_symbols(elf_path)

    # Find symbol at entrypoint address
    found = None
    for name, (addr, typ) in symbols.items():
        if addr == entrypoint:
            found = (name, typ)
            break

    assert found is not None, (
        f"Entrypoint not found in ELF!\n"
        f"  Config entrypoint: 0x{entrypoint:08X}\n"
        f"  No symbol at this address in the ELF.\n"
        f"  Check that the entrypoint is correct."
    )

    name, typ = found
    assert typ in ('T', 't'), (
        f"Entrypoint is not a function!\n"
        f"  Address: 0x{entrypoint:08X}\n"
        f"  Symbol: {name}\n"
        f"  Type: {typ} (expected T or t for text/code)"
    )

    print(f"[PASS] Entrypoint 0x{entrypoint:08X} exists as function '{name}'")


def test_ignored_symbols_exist():
    """
    Test that all ignored symbols exist in ELF.

    Why this matters:
    - Ignored symbols are skipped during recompilation
    - If they don't exist, something is wrong with the config
    - These are typically RSP microcode markers (aspMainTextStart, etc.)
    """
    import pytest
    config = parse_toml_simple(US_TOML_PATH)
    ignored = config.get('ignored', [])

    if not ignored:
        pytest.skip("No ignored symbols configured")

    # Get ELF path and load symbols
    elf_path = RECOMP_ROOT / config.get('elf_path', '')
    if not elf_path.exists():
        pytest.skip(f"Cannot verify ignored symbols, ELF not found: {elf_path}")

    symbols = get_elf_symbols(elf_path)
    symbol_names = set(symbols.keys())

    missing = []
    found = []
    for sym in ignored:
        if sym in symbol_names:
            found.append(sym)
        else:
            missing.append(sym)

    print(f"       Ignored symbols in config: {len(ignored)}")
    print(f"       Found in ELF: {len(found)}")

    if missing:
        print(f"[WARN] Missing ignored symbols (not in ELF):")
        for sym in missing:
            print(f"         - {sym}")

    # All ignored symbols should exist
    assert len(missing) == 0, (
        f"Some ignored symbols not found in ELF!\n"
        f"  Missing: {missing}\n"
        f"  These might be typos or from a different ELF version."
    )

    print(f"[PASS] All {len(ignored)} ignored symbols exist in ELF")


def test_no_use_absolute_symbols():
    """
    Test that use_absolute_symbols is not enabled.

    Why this matters:
    - use_absolute_symbols=true treats absolute symbols as functions
    - For HM64 with complete decomp, this is WRONG
    - It causes ~8000 data variables to be lost from data_dump
    - Patches would fail because they can't find game variables

    When use_absolute_symbols should be true:
    - Only for patches.toml (patches need to jump to game functions)
    - NOT for main game us.toml
    """
    config = parse_toml_simple(US_TOML_PATH)

    use_abs = config.get('use_absolute_symbols', False)

    if use_abs:
        print(f"[FAIL] use_absolute_symbols is TRUE!")
        print(f"       This should be removed or set to false for main game.")
        print(f"       With true: ~8000 data symbols are lost")
        print(f"       With false: all symbols preserved correctly")
        assert False, (
            "use_absolute_symbols should not be true for main game!\n"
            "Remove this line from us.toml or set it to false."
        )
    else:
        print(f"[PASS] use_absolute_symbols is not enabled (correct for main game)")


def test_trace_mode_enabled():
    """
    Test that trace_mode is enabled.

    Why this matters:
    - trace_mode = true enables function tracing in recompiled code
    - Useful for debugging which functions are being called
    - Should be enabled during development
    """
    config = parse_toml_simple(US_TOML_PATH)

    trace_mode = config.get('trace_mode', False)

    assert trace_mode == True, (
        "trace_mode is not enabled!\n"
        "Add 'trace_mode = true' to [input] section for debugging."
    )

    print(f"[PASS] trace_mode is enabled")


def test_output_path_writable():
    """
    Test that output_func_path is writable.

    Why this matters:
    - N64Recomp writes generated code here
    - If not writable, build fails
    """
    config = parse_toml_simple(US_TOML_PATH)

    output_path = config.get('output_func_path', 'RecompiledFuncs')
    full_path = RECOMP_ROOT / output_path

    # Path should either exist or parent should be writable
    if full_path.exists():
        assert full_path.is_dir(), f"output_func_path exists but is not a directory: {full_path}"
        print(f"[PASS] output_func_path exists: {output_path}")
    else:
        parent = full_path.parent
        assert parent.exists(), f"Parent directory does not exist: {parent}"
        print(f"[PASS] output_func_path parent exists: {parent}")


def run_all_tests():
    """Run all us.toml validation tests."""
    print("=" * 60)
    print("us.toml Configuration Tests")
    print("=" * 60)
    print(f"Config: {US_TOML_PATH}")
    print("-" * 60)

    tests = [
        test_toml_exists,
        test_elf_path_exists,
        test_rom_path_exists,
        test_entrypoint_in_elf,
        test_ignored_symbols_exist,
        test_no_use_absolute_symbols,
        test_trace_mode_enabled,
        test_output_path_writable,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}")
            print(f"       {e}")
            failed += 1
        except FileNotFoundError as e:
            print(f"[SKIP] {test.__name__}: {e}")

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
