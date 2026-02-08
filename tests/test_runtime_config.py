"""
Test Modern Runtime configuration values.

Validates that:
1. ROM hash in main.cpp matches expected HM64 hash
2. Program ID is set to HM64 (determines cache folder)
3. Program name is set to HM64 (window title)
4. Game ID and internal name are correct
"""

import re
from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_CPP = REPO_ROOT / "src" / "main" / "main.cpp"
CONFIG_H = REPO_ROOT / "include" / "zelda_config.h"

# Expected values
EXPECTED_ROM_HASH = 0x68B2C3755C527305
EXPECTED_PROGRAM_ID = "HarvestMoon64Recompiled"
EXPECTED_PROGRAM_NAME = "Harvest Moon 64: Recompiled"
EXPECTED_INTERNAL_NAME = "HARVESTMOON64"
EXPECTED_GAME_ID = "hm64.n64.us.1.0"
EXPECTED_MOD_GAME_ID = "hm64"

# Cache locations (for reference)
# macOS: ~/Library/Application Support/{program_id}/
# Linux: ~/.config/{program_id}/
# Windows: %LOCALAPPDATA%/{program_id}/


def read_file(path: Path) -> str:
    """Read a source file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text()


def test_main_cpp_exists():
    """Test that main.cpp exists."""
    assert MAIN_CPP.exists(), f"main.cpp not found: {MAIN_CPP}"
    print(f"[PASS] main.cpp exists: {MAIN_CPP}")


def test_config_h_exists():
    """Test that zelda_config.h exists."""
    assert CONFIG_H.exists(), f"zelda_config.h not found: {CONFIG_H}"
    print(f"[PASS] zelda_config.h exists: {CONFIG_H}")


def test_rom_hash_in_main():
    """
    Test that ROM hash in main.cpp matches expected HM64 hash.

    The rom_hash is used by Modern Runtime to verify the ROM.
    If wrong, the game refuses to start.
    """
    content = read_file(MAIN_CPP)

    # Look for: .rom_hash = 0x68B2C3755C527305ULL
    match = re.search(r'\.rom_hash\s*=\s*(0x[0-9A-Fa-f]+)', content)

    assert match, "Could not find .rom_hash in main.cpp"

    found_hash = int(match.group(1), 16)

    assert found_hash == EXPECTED_ROM_HASH, (
        f"ROM hash mismatch in main.cpp!\n"
        f"  Got:      0x{found_hash:016X}\n"
        f"  Expected: 0x{EXPECTED_ROM_HASH:016X}\n"
        f"  Update .rom_hash in main.cpp to match HM64 US ROM."
    )

    print(f"[PASS] ROM hash in main.cpp: 0x{found_hash:016X}")


def test_internal_name():
    """Test that internal_name is set to Harvest Moon 64."""
    content = read_file(MAIN_CPP)

    # Look for: .internal_name = "Harvest Moon 64"
    match = re.search(r'\.internal_name\s*=\s*"([^"]+)"', content)

    assert match, "Could not find .internal_name in main.cpp"

    found_name = match.group(1)

    assert found_name == EXPECTED_INTERNAL_NAME, (
        f"Internal name mismatch in main.cpp!\n"
        f"  Got:      {found_name}\n"
        f"  Expected: {EXPECTED_INTERNAL_NAME}"
    )

    print(f"[PASS] Internal name: {found_name}")


def test_game_id():
    """Test that game_id is set correctly for HM64."""
    content = read_file(MAIN_CPP)

    # Look for: .game_id = u8"hm64.n64.us.1.0"
    match = re.search(r'\.game_id\s*=\s*u8"([^"]+)"', content)

    assert match, "Could not find .game_id in main.cpp"

    found_id = match.group(1)

    assert found_id == EXPECTED_GAME_ID, (
        f"Game ID mismatch in main.cpp!\n"
        f"  Got:      {found_id}\n"
        f"  Expected: {EXPECTED_GAME_ID}"
    )

    print(f"[PASS] Game ID: {found_id}")


def test_mod_game_id():
    """Test that mod_game_id is set correctly for HM64."""
    content = read_file(MAIN_CPP)

    # Look for: .mod_game_id = "hm64"
    match = re.search(r'\.mod_game_id\s*=\s*"([^"]+)"', content)

    assert match, "Could not find .mod_game_id in main.cpp"

    found_id = match.group(1)

    assert found_id == EXPECTED_MOD_GAME_ID, (
        f"Mod game ID mismatch in main.cpp!\n"
        f"  Got:      {found_id}\n"
        f"  Expected: {EXPECTED_MOD_GAME_ID}"
    )

    print(f"[PASS] Mod game ID: {found_id}")


def test_program_id():
    """
    Test that program_id is set to HM64.

    The program_id determines the cache/config folder location:
    - macOS: ~/Library/Application Support/{program_id}/
    - Linux: ~/.config/{program_id}/
    - Windows: %LOCALAPPDATA%/{program_id}/
    """
    content = read_file(CONFIG_H)

    # Look for: program_id = u8"HarvestMoon64Recompiled"
    match = re.search(r'program_id\s*=\s*u8"([^"]+)"', content)

    assert match, "Could not find program_id in zelda_config.h"

    found_id = match.group(1)

    assert found_id == EXPECTED_PROGRAM_ID, (
        f"Program ID mismatch in zelda_config.h!\n"
        f"  Got:      {found_id}\n"
        f"  Expected: {EXPECTED_PROGRAM_ID}\n"
        f"  Cache folder will be wrong if not updated."
    )

    print(f"[PASS] Program ID: {found_id}")
    print(f"       Cache: ~/Library/Application Support/{found_id}/")


def test_program_name():
    """
    Test that program_name is set to HM64.

    The program_name is displayed in the window title.
    """
    content = read_file(CONFIG_H)

    # Look for: program_name = "Harvest Moon 64: Recompiled"
    match = re.search(r'program_name\s*=\s*"([^"]+)"', content)

    assert match, "Could not find program_name in zelda_config.h"

    found_name = match.group(1)

    assert found_name == EXPECTED_PROGRAM_NAME, (
        f"Program name mismatch in zelda_config.h!\n"
        f"  Got:      {found_name}\n"
        f"  Expected: {EXPECTED_PROGRAM_NAME}"
    )

    print(f"[PASS] Program name: {found_name}")


def test_no_zelda_references_in_game_config():
    """
    Test that game-specific config doesn't have leftover MK64/Zelda references.

    Checks that key identifiers have been updated to HM64.
    """
    content = read_file(MAIN_CPP)

    # These should NOT be found in game config section
    old_patterns = [
        (r'\.internal_name\s*=\s*"[^"]*[Zz]elda[^"]*"', 'internal_name still contains Zelda'),
        (r'\.game_id\s*=\s*u8"mk64\.', 'game_id still starts with mk64.'),
        (r'\.mod_game_id\s*=\s*"mk64"', 'mod_game_id is still mk64'),
    ]

    for pattern, msg in old_patterns:
        match = re.search(pattern, content)
        assert not match, f"Found old reference: {msg}"

    print("[PASS] No old MK64/Zelda references in game config")


def run_all_tests():
    """Run all runtime config tests."""
    print("=" * 60)
    print("Runtime Config Tests")
    print("=" * 60)
    print(f"main.cpp: {MAIN_CPP}")
    print(f"config.h: {CONFIG_H}")
    print("-" * 60)

    tests = [
        test_main_cpp_exists,
        test_config_h_exists,
        test_rom_hash_in_main,
        test_internal_name,
        test_game_id,
        test_mod_game_id,
        test_program_id,
        test_program_name,
        test_no_zelda_references_in_game_config,
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
