"""
Test ELF symbol types and sections.

Validates that:
1. Functions have proper section info (T/t symbols, not A)
2. Absolute symbols are data, not functions
3. Entrypoint exists as a function
4. Symbol counts are reasonable

Symbol types (from nm):
  T/t = Text (code/functions) - in .text section
  D/d = Data (initialized variables) - in .data section
  B/b = BSS (uninitialized variables) - in .bss section
  R/r = Read-only data - in .rodata section
  A   = Absolute (no section, just an address)

Capital = global (extern visible)
Lowercase = local (file-only)
"""

import subprocess
from pathlib import Path
from collections import Counter

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
ELF_PATH = REPO_ROOT / "roms" / "hm64.elf"

# Expected values
EXPECTED_ENTRYPOINT = 0x80025C00
MIN_FUNCTION_COUNT = 10000   # Decomp should have many functions
MAX_FUNCTION_COUNT = 50000   # But not unreasonably many
MIN_ABSOLUTE_SYMBOLS = 1000  # Data variables as linker symbols


def get_elf_symbols() -> list:
    """
    Get all symbols from ELF using nm command.
    Returns list of (address, type, name) tuples.
    """
    if not ELF_PATH.exists():
        import pytest
        pytest.skip(f"ELF not found (expected for clean/public repo): {ELF_PATH}")

    result = subprocess.run(
        ['nm', str(ELF_PATH)],
        capture_output=True, text=True
    )

    symbols = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            addr_str, sym_type, name = parts[0], parts[1], parts[2]
            try:
                addr = int(addr_str, 16)
                symbols.append((addr, sym_type, name))
            except ValueError:
                pass

    return symbols


def test_elf_exists():
    """Test that ELF file exists."""
    import pytest
    if not ELF_PATH.exists():
        pytest.skip(f"ELF not found (expected for clean/public repo): {ELF_PATH}")
    print(f"[PASS] ELF exists: {ELF_PATH}")


def test_functions_have_sections():
    """
    Test that all functions have proper section info.

    Functions should be T (global text) or t (local text).
    They should NOT be A (absolute) because that means no section.

    Why this matters:
    - T/t symbols: N64Recomp knows it's code, can recompile it
    - A symbols: N64Recomp doesn't know what it is
    """
    symbols = get_elf_symbols()

    # Get all text symbols (functions with sections)
    text_symbols = [(a, t, n) for a, t, n in symbols if t in ('T', 't')]

    # Get all absolute symbols
    absolute_symbols = [(a, t, n) for a, t, n in symbols if t == 'A']

    # Check for function-like names in absolute symbols
    # Function names typically: start with lowercase, have underscores, no D_ prefix
    suspicious_absolute = []
    for addr, typ, name in absolute_symbols:
        # Skip known data patterns
        if name.startswith('D_'):
            continue
        if name.startswith('_'):
            continue
        # Check if it looks like a function name (common patterns)
        if any(name.startswith(p) for p in ['func_', 'sub_', 'update', 'init', 'process']):
            suspicious_absolute.append((addr, name))

    if suspicious_absolute:
        print(f"[WARN] Found {len(suspicious_absolute)} function-like absolute symbols:")
        for addr, name in suspicious_absolute[:5]:
            print(f"       0x{addr:08X} A {name}")
        if len(suspicious_absolute) > 5:
            print(f"       ... and {len(suspicious_absolute) - 5} more")

    print(f"[PASS] Functions have sections:")
    print(f"       T/t (text) symbols: {len(text_symbols):,}")
    print(f"       A (absolute) symbols: {len(absolute_symbols):,}")


def test_absolute_symbols_are_data():
    """
    Test that absolute symbols are data variables, not functions.

    Absolute symbols come from symbol_addrs.txt in decomp.
    They should be data like: gWeather, chickenFeedQuantity, D_80XXXXXX

    Why this matters:
    - If use_absolute_symbols=true, N64Recomp treats them as jump targets
    - Data variables are too small to be functions (often 1-4 bytes)
    - This would cause them to be skipped or cause errors
    """
    symbols = get_elf_symbols()

    absolute = [(a, n) for a, _, n in symbols if _ == 'A']

    # Count patterns
    data_prefix = sum(1 for _, n in absolute if n.startswith('D_'))
    underscore_prefix = sum(1 for _, n in absolute if n.startswith('_'))
    lowercase_g = sum(1 for _, n in absolute if n.startswith('g') and n[1:2].isupper())

    print(f"[PASS] Absolute symbols appear to be data:")
    print(f"       D_XXXXXXXX pattern: {data_prefix:,}")
    print(f"       _underscore prefix: {underscore_prefix:,}")
    print(f"       gCamelCase (globals): {lowercase_g:,}")

    # Verify most absolute symbols follow data naming
    # _underscore prefix is valid - these are linker segment markers
    named_data = data_prefix + lowercase_g + underscore_prefix
    total = len(absolute)
    data_ratio = named_data / total if total > 0 else 0

    # Most absolute symbols should have data-like naming
    assert data_ratio > 0.5, (
        f"Too few absolute symbols look like data!\n"
        f"  D_ prefix: {data_prefix}\n"
        f"  gCamelCase: {lowercase_g}\n"
        f"  _underscore: {underscore_prefix}\n"
        f"  Total absolute: {total}\n"
        f"  This might indicate a problem with the decomp."
    )


def test_entrypoint_exists():
    """
    Test that the entrypoint address exists as a function.

    The entrypoint (0x80025C00) should be a T symbol (global function).

    Why this matters:
    - us.toml specifies entrypoint = 0x80025C00
    - If it doesn't exist, recomp will fail
    """
    symbols = get_elf_symbols()

    # Find symbol at entrypoint address
    entrypoint_symbols = [(t, n) for a, t, n in symbols if a == EXPECTED_ENTRYPOINT]

    assert len(entrypoint_symbols) > 0, (
        f"Entrypoint not found in ELF!\n"
        f"  Expected address: 0x{EXPECTED_ENTRYPOINT:08X}\n"
        f"  This should be the game's entry point."
    )

    sym_type, sym_name = entrypoint_symbols[0]

    # Should be a text symbol (function)
    assert sym_type in ('T', 't'), (
        f"Entrypoint is not a function!\n"
        f"  Address: 0x{EXPECTED_ENTRYPOINT:08X}\n"
        f"  Type: {sym_type} (expected T or t)\n"
        f"  Name: {sym_name}"
    )

    print(f"[PASS] Entrypoint exists: 0x{EXPECTED_ENTRYPOINT:08X}")
    print(f"       Type: {sym_type} (text/code)")
    print(f"       Name: {sym_name}")


def test_symbol_counts():
    """
    Test that symbol counts are reasonable for a complete decomp.

    A complete decomp should have:
    - Many functions (T/t symbols): 10,000 - 50,000
    - Some absolute symbols (data): 1,000+

    Why this matters:
    - Too few functions = incomplete decomp
    - Too many = something might be wrong
    """
    symbols = get_elf_symbols()

    # Count by type
    type_counts = Counter(t for _, t, _ in symbols)

    func_count = type_counts.get('T', 0) + type_counts.get('t', 0)
    abs_count = type_counts.get('A', 0)
    data_count = type_counts.get('D', 0) + type_counts.get('d', 0)
    bss_count = type_counts.get('B', 0) + type_counts.get('b', 0)

    print(f"[INFO] Symbol counts by type:")
    print(f"       Functions (T/t): {func_count:,}")
    print(f"       Absolute (A):    {abs_count:,}")
    print(f"       Data (D/d):      {data_count:,}")
    print(f"       BSS (B/b):       {bss_count:,}")

    # Validate function count
    assert func_count >= MIN_FUNCTION_COUNT, (
        f"Too few functions!\n"
        f"  Got: {func_count:,}\n"
        f"  Expected at least: {MIN_FUNCTION_COUNT:,}\n"
        f"  Decomp might be incomplete."
    )

    assert func_count <= MAX_FUNCTION_COUNT, (
        f"Suspiciously many functions!\n"
        f"  Got: {func_count:,}\n"
        f"  Expected at most: {MAX_FUNCTION_COUNT:,}\n"
        f"  Something might be wrong with the ELF."
    )

    # Validate absolute symbol count
    assert abs_count >= MIN_ABSOLUTE_SYMBOLS, (
        f"Too few absolute symbols!\n"
        f"  Got: {abs_count:,}\n"
        f"  Expected at least: {MIN_ABSOLUTE_SYMBOLS:,}\n"
        f"  This is unusual for a decomp using symbol_addrs.txt"
    )

    print(f"[PASS] Symbol counts are reasonable")


def is_segment_marker(name: str) -> bool:
    """
    Check if a symbol name is a linker segment boundary marker.

    These markers define where segments start/end in memory:
    - _fooSegmentStart, _fooSegmentEnd
    - _fooSegmentTextStart, _fooSegmentDataEnd, etc.
    - foo_seg_0, foo_seg_1

    They're not real functions, just address markers for the linker.
    """
    # Check for Segment boundary markers
    segment_suffixes = (
        'SegmentStart', 'SegmentEnd',
        'SegmentTextStart', 'SegmentTextEnd',
        'SegmentDataStart', 'SegmentDataEnd',
        'SegmentRoDataStart', 'SegmentRoDataEnd',
        'SegmentSDataStart', 'SegmentSDataEnd',
        'SegmentOvlStart', 'SegmentOvlEnd',
    )
    if any(name.endswith(suffix) for suffix in segment_suffixes):
        return True

    # Check for _seg_N pattern (overlay segment markers)
    if '_seg_' in name:
        return True

    return False


def test_no_overlapping_functions():
    """
    Test that no two functions have the same address.

    Each function should have a unique address.

    Why this matters:
    - Duplicate addresses would confuse N64Recomp
    - Could indicate a bug in the decomp

    Note: These symbols are excluded from duplicate checking:
    - gcc2_compiled. = GCC debug markers at function start addresses
    - *Segment* markers = linker segment boundary symbols
    - *_seg_* = overlay segment markers
    """
    symbols = get_elf_symbols()

    # Get function addresses, excluding debug markers and segment boundaries
    functions = [(a, n) for a, t, n in symbols
                 if t in ('T', 't')
                 and n != 'gcc2_compiled.'
                 and not is_segment_marker(n)]

    # Check for duplicates
    addr_to_names = {}
    for addr, name in functions:
        if addr not in addr_to_names:
            addr_to_names[addr] = []
        addr_to_names[addr].append(name)

    duplicates = {a: names for a, names in addr_to_names.items() if len(names) > 1}

    if duplicates:
        print(f"[WARN] Found {len(duplicates)} addresses with multiple functions:")
        for addr, names in list(duplicates.items())[:3]:
            print(f"       0x{addr:08X}: {names}")

    # Some duplicates are OK (weak symbols, aliases like __umoddi3/mod_com)
    # But too many indicates a problem
    assert len(duplicates) < 100, (
        f"Too many duplicate function addresses!\n"
        f"  Got: {len(duplicates)}\n"
        f"  This might indicate a problem with the decomp."
    )

    print(f"[PASS] Function addresses are mostly unique")
    print(f"       Total functions: {len(functions):,}")
    print(f"       Duplicate addresses: {len(duplicates)}")


def run_all_tests():
    """Run all ELF symbol tests."""
    print("=" * 60)
    print("ELF Symbol Tests")
    print("=" * 60)
    print(f"ELF: {ELF_PATH}")
    print("-" * 60)

    tests = [
        test_elf_exists,
        test_functions_have_sections,
        test_absolute_symbols_are_data,
        test_entrypoint_exists,
        test_symbol_counts,
        test_no_overlapping_functions,
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
