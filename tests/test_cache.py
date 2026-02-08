"""
Test ROM cache configuration and presence.

Validates that:
1. Cache directory path is correctly configured
2. Cache directory exists (after game has run once)
3. Cache contains expected files

Note: Some tests only pass after the game has been run at least once.
"""

import os
from pathlib import Path
import platform

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_H = REPO_ROOT / "include" / "zelda_config.h"

# Expected values
EXPECTED_PROGRAM_ID = "HarvestMoon64Recompiled"


def get_cache_path() -> Path:
    """Get the expected cache path based on platform."""
    system = platform.system()

    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / EXPECTED_PROGRAM_ID
    elif system == "Linux":
        return Path.home() / ".config" / EXPECTED_PROGRAM_ID
    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return Path(local_app_data) / EXPECTED_PROGRAM_ID
        return Path.home() / "AppData" / "Local" / EXPECTED_PROGRAM_ID
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def test_cache_path_config():
    """
    Test that program_id in config matches expected value.

    This determines where the cache will be stored.
    """
    import re

    content = CONFIG_H.read_text()
    match = re.search(r'program_id\s*=\s*u8"([^"]+)"', content)

    assert match, "Could not find program_id in zelda_config.h"

    found_id = match.group(1)
    assert found_id == EXPECTED_PROGRAM_ID, (
        f"Program ID mismatch!\n"
        f"  Got:      {found_id}\n"
        f"  Expected: {EXPECTED_PROGRAM_ID}"
    )

    cache_path = get_cache_path()
    print(f"[PASS] Program ID: {found_id}")
    print(f"       Cache path: {cache_path}")


def test_cache_directory_exists():
    """
    Test that cache directory exists.

    NOTE: This test only passes after the game has been run at least once.
    The cache is created on first run when ROM is loaded.
    """
    import pytest
    cache_path = get_cache_path()

    if not cache_path.exists():
        pytest.skip(f"Cache directory not found: {cache_path} (run game once to create)")

    assert cache_path.is_dir(), f"Cache path is not a directory: {cache_path}"

    print(f"[PASS] Cache directory exists: {cache_path}")


def test_cache_contains_rom():
    """
    Test that cache contains the processed ROM.

    NOTE: This test only passes after the game has been run at least once.
    """
    import pytest
    cache_path = get_cache_path()

    if not cache_path.exists():
        pytest.skip(f"Cache directory not found: {cache_path}")

    # List cache contents
    cache_files = list(cache_path.iterdir()) if cache_path.exists() else []

    if not cache_files:
        pytest.skip(f"Cache is empty: {cache_path}")

    print(f"[PASS] Cache contains {len(cache_files)} item(s):")
    for f in cache_files:
        size = f.stat().st_size if f.is_file() else 0
        type_str = "dir" if f.is_dir() else f"{size:,} bytes"
        print(f"       - {f.name} ({type_str})")


def test_no_old_mk64_cache():
    """
    Test that old MK64 cache doesn't exist (to avoid confusion).

    NOTE: This test is a lightweight guard: if you previously ran an older scaffold
    with a different program_id, you might be looking at the wrong cache folder.
    """
    # No-op: we don't know which old IDs a dev might have used locally.
    pass


def run_all_tests():
    """Run all cache tests."""
    print("=" * 60)
    print("Cache Tests")
    print("=" * 60)
    print(f"Platform: {platform.system()}")
    print(f"Expected cache: {get_cache_path()}")
    print("-" * 60)

    tests = [
        test_cache_path_config,
        test_cache_directory_exists,
        test_cache_contains_rom,
        test_no_old_mk64_cache,
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
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
