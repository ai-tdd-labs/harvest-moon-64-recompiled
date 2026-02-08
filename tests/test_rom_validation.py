"""
Test ROM file validation.

Validates that:
1. ROM file exists and is readable
2. ROM has correct N64 magic bytes
3. ROM has correct title
4. ROM has expected size
5. ROM has correct XXH3 hash (same as Modern Runtime expects)
"""

import struct
from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = REPO_ROOT / "roms" / "baserom.us.z64"

# Expected values
EXPECTED_ROM_SIZE = 0x1000000  # 16MB
EXPECTED_TITLE = b"HARVESTMOON64"  # ROM title (no spaces in actual ROM)
N64_MAGIC_Z64 = 0x80371240  # Big-endian (z64 format)

# =============================================================================
# ROM HASH (XXH3)
# =============================================================================
# Dit is dezelfde hash die Modern Runtime verwacht in src/main/main.cpp:
#   .rom_hash = 0x68B2C3755C527305ULL
#
# Modern Runtime gebruikt XXH3_64bits() om de ROM te hashen.
# Als deze hash niet matched, weigert de game te starten.
# =============================================================================
EXPECTED_ROM_HASH = 0x68B2C3755C527305


def load_rom() -> bytes:
    """Load the ROM file."""
    import pytest
    if not ROM_PATH.exists():
        pytest.skip(f"ROM not found (expected for clean/public repo): {ROM_PATH}")
    return ROM_PATH.read_bytes()


def test_rom_exists():
    """Test that ROM file exists and is readable."""
    import pytest
    if not ROM_PATH.exists():
        pytest.skip(f"ROM not found (expected for clean/public repo): {ROM_PATH}")
    assert ROM_PATH.is_file(), f"ROM path is not a file: {ROM_PATH}"

    # Try to read first byte to verify it's readable
    with open(ROM_PATH, 'rb') as f:
        first_byte = f.read(1)
        assert len(first_byte) == 1, "ROM file is empty or unreadable"

    print(f"[PASS] ROM exists: {ROM_PATH}")


def test_rom_magic_bytes():
    """
    Test that ROM has correct N64 magic bytes.

    N64 ROMs start with specific magic bytes that indicate format:
    - 0x80371240 = z64 (big-endian, native N64 format)
    - 0x37804012 = n64 (byte-swapped)
    - 0x40123780 = v64 (word-swapped)

    We expect z64 format (big-endian).
    """
    rom = load_rom()

    # Read first 4 bytes as big-endian uint32
    magic = struct.unpack('>I', rom[:4])[0]

    assert magic == N64_MAGIC_Z64, (
        f"ROM magic bytes mismatch!\n"
        f"  Got:      0x{magic:08X}\n"
        f"  Expected: 0x{N64_MAGIC_Z64:08X} (z64 big-endian format)\n"
        f"  If you have n64/v64 format, convert to z64 first."
    )

    print(f"[PASS] ROM magic bytes: 0x{magic:08X} (z64 format)")


def test_rom_title():
    """
    Test that ROM has correct game title in header.

    N64 ROM header contains game title at offset 0x20,
    padded with spaces to 20 bytes.
    """
    rom = load_rom()

    # Title is at offset 0x20, length 20 bytes
    title_offset = 0x20
    title_length = 20
    title_bytes = rom[title_offset:title_offset + title_length]

    # Strip trailing spaces/nulls
    title = title_bytes.rstrip(b'\x00 ')

    assert EXPECTED_TITLE in title_bytes, (
        f"ROM title mismatch!\n"
        f"  Got:      {title_bytes!r}\n"
        f"  Expected: {EXPECTED_TITLE!r}\n"
        f"  This might not be the correct ROM."
    )

    print(f"[PASS] ROM title: {title.decode('ascii', errors='replace')}")


def test_rom_size():
    """
    Test that ROM has expected size.

    Harvest Moon 64 US ROM should be exactly 16MB (0x1000000 bytes).
    """
    rom = load_rom()
    actual_size = len(rom)

    assert actual_size == EXPECTED_ROM_SIZE, (
        f"ROM size mismatch!\n"
        f"  Got:      0x{actual_size:X} ({actual_size:,} bytes)\n"
        f"  Expected: 0x{EXPECTED_ROM_SIZE:X} ({EXPECTED_ROM_SIZE:,} bytes)\n"
        f"  ROM might be truncated or padded."
    )

    print(f"[PASS] ROM size: 0x{actual_size:X} ({actual_size // 1024 // 1024}MB)")


def test_rom_not_empty():
    """Test that ROM is not filled with zeros or 0xFF."""
    rom = load_rom()

    # Check first 1KB isn't all zeros
    first_kb = rom[:1024]
    assert first_kb != b'\x00' * 1024, "ROM first 1KB is all zeros!"

    # Check first 1KB isn't all 0xFF (erased flash)
    assert first_kb != b'\xFF' * 1024, "ROM first 1KB is all 0xFF!"

    # Check some code exists (should have variety of bytes)
    unique_bytes = len(set(first_kb))
    assert unique_bytes > 50, (
        f"ROM has suspiciously low byte variety ({unique_bytes} unique bytes in first 1KB)"
    )

    print(f"[PASS] ROM has valid data ({unique_bytes} unique bytes in first 1KB)")


def test_rom_hash():
    """
    Test that ROM has correct XXH3 hash.

    Modern Runtime (N64ModernRuntime) uses XXH3_64bits() to verify ROMs.
    The expected hash is defined in src/main/main.cpp as .rom_hash

    Why this matters:
    - If hash doesn't match, Modern Runtime refuses to load the ROM
    - Wrong ROM version = wrong hash = game won't start
    - This ensures we have the exact correct US ROM
    """
    import pytest
    try:
        import xxhash
    except ImportError:
        pytest.skip("xxhash library not installed (pip install xxhash)")

    rom = load_rom()

    # Calculate XXH3 64-bit hash (same as Modern Runtime)
    calculated_hash = xxhash.xxh3_64(rom).intdigest()

    assert calculated_hash == EXPECTED_ROM_HASH, (
        f"ROM hash mismatch!\n"
        f"  Got:      0x{calculated_hash:016X}\n"
        f"  Expected: 0x{EXPECTED_ROM_HASH:016X}\n"
        f"  This ROM won't work with Modern Runtime.\n"
        f"  Make sure you have the correct US version."
    )

    print(f"[PASS] ROM hash: 0x{calculated_hash:016X}")
    print(f"       Matches Modern Runtime expected hash ✓")


def run_all_tests():
    """Run all ROM validation tests."""
    print("=" * 60)
    print("ROM Validation Tests")
    print("=" * 60)
    print(f"ROM: {ROM_PATH}")
    print("-" * 60)

    tests = [
        test_rom_exists,
        test_rom_magic_bytes,
        test_rom_title,
        test_rom_size,
        test_rom_not_empty,
        test_rom_hash,
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
