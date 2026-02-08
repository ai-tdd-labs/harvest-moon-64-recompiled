"""
Test that trace macros are properly inserted in RecompiledFuncs.

Validates that:
1. TRACE_ENTRY() is present in all funcs_*.c files
2. TRACE_RETURN() is present in all funcs_*.c files
3. trace.h is included in all funcs_*.c files
4. trace.h exists in include directory
5. Tracing is OFF by default (no log spam / less overhead), but can be enabled explicitly

Why these tests matter:
- trace_mode = true in TOML only generates trace calls
- Without trace.h, code won't compile
- With tracing OFF by default, TRACE_* calls become no-ops unless enabled
- Missing trace calls = can't debug function flow
"""

from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
RECOMPILED_FUNCS = REPO_ROOT / "RecompiledFuncs"
TRACE_HEADER = REPO_ROOT / "include" / "trace.h"
CMAKE_LISTS = REPO_ROOT / "CMakeLists.txt"


def test_trace_header_exists():
    """Test that trace.h exists in include directory."""
    assert TRACE_HEADER.exists(), (
        f"trace.h not found at {TRACE_HEADER}\n"
        f"This file is required for TRACE_ENTRY/TRACE_RETURN to work."
    )
    print(f"[PASS] trace.h exists: {TRACE_HEADER}")


def test_trace_header_defaults_off():
    """Test that trace.h defaults RECOMP_TRACE to 0 unless overridden."""
    if not TRACE_HEADER.exists():
        import pytest
        pytest.skip("trace.h not found")

    content = TRACE_HEADER.read_text()

    # Default should be OFF. (Build can still enable it via -DRECOMP_TRACE=1.)
    assert '#define RECOMP_TRACE 0' in content, (
        "trace.h should default RECOMP_TRACE to 0 to avoid log spam and overhead.\n"
        "Expected '#define RECOMP_TRACE 0' under '#ifndef RECOMP_TRACE'."
    )

    # Check for TRACE_ENTRY macro
    assert 'TRACE_ENTRY' in content, (
        "trace.h does not define TRACE_ENTRY macro!"
    )

    # Check for TRACE_RETURN macro
    assert 'TRACE_RETURN' in content, (
        "trace.h does not define TRACE_RETURN macro!"
    )

    print("[PASS] trace.h defaults tracing off and defines trace macros")


def test_cmake_trace_option_defaults_off():
    """Test that CMake defaults tracing OFF, with an explicit toggle."""
    if not CMAKE_LISTS.exists():
        import pytest
        pytest.skip("CMakeLists.txt not found")

    content = CMAKE_LISTS.read_text()

    assert 'option(RECOMP_ENABLE_TRACE "Enable trace logging in recompiled functions" OFF)' in content, (
        "CMakeLists.txt should define RECOMP_ENABLE_TRACE default OFF."
    )
    assert 'add_compile_definitions(RECOMP_TRACE=1)' in content, (
        "CMakeLists.txt should enable RECOMP_TRACE only when RECOMP_ENABLE_TRACE is ON."
    )
    print("[PASS] CMake trace option exists and defaults OFF")


def test_recompiled_funcs_include_trace():
    """Test that all funcs_*.c files include trace.h."""
    func_files = list(RECOMPILED_FUNCS.glob("funcs_*.c"))

    if not func_files:
        import pytest
        pytest.skip("No funcs_*.c files found - run N64Recomp first")

    missing_include = []

    for func_file in func_files:
        content = func_file.read_text()
        # Check first 20 lines for include
        first_lines = '\n'.join(content.split('\n')[:20])
        if '#include "trace.h"' not in first_lines:
            missing_include.append(func_file.name)

    assert len(missing_include) == 0, (
        f"These files are missing '#include \"trace.h\"':\n"
        f"  {missing_include}\n"
        f"Ensure trace_mode = true in TOML and re-run N64Recomp."
    )

    print(f"[PASS] All {len(func_files)} funcs_*.c files include trace.h")


def test_recompiled_funcs_have_trace_entry():
    """Test that all funcs_*.c files contain TRACE_ENTRY() calls."""
    func_files = list(RECOMPILED_FUNCS.glob("funcs_*.c"))

    if not func_files:
        import pytest
        pytest.skip("No funcs_*.c files found - run N64Recomp first")

    files_without_trace = []
    total_trace_calls = 0

    for func_file in func_files:
        content = func_file.read_text()
        count = content.count('TRACE_ENTRY()')
        if count == 0:
            files_without_trace.append(func_file.name)
        total_trace_calls += count

    assert len(files_without_trace) == 0, (
        f"These files have no TRACE_ENTRY() calls:\n"
        f"  {files_without_trace}\n"
        f"Ensure trace_mode = true in TOML and re-run N64Recomp."
    )

    print(f"[PASS] Found {total_trace_calls} TRACE_ENTRY() calls across {len(func_files)} files")


def test_recompiled_funcs_have_trace_return():
    """Test that funcs_*.c files contain TRACE_RETURN() calls."""
    func_files = list(RECOMPILED_FUNCS.glob("funcs_*.c"))

    if not func_files:
        import pytest
        pytest.skip("No funcs_*.c files found - run N64Recomp first")

    total_trace_returns = 0

    for func_file in func_files:
        content = func_file.read_text()
        count = content.count('TRACE_RETURN()')
        total_trace_returns += count

    # TRACE_RETURN is optional (some functions may not have returns)
    # But we should have at least some
    assert total_trace_returns > 0, (
        f"No TRACE_RETURN() calls found in any funcs_*.c files!\n"
        f"This might indicate a problem with trace generation."
    )

    print(f"[PASS] Found {total_trace_returns} TRACE_RETURN() calls")


def test_trace_count_reasonable():
    """
    Test that trace call count is reasonable for HM64.

    HM64 has ~26,494 functions, so we expect roughly:
    - ~26,000+ TRACE_ENTRY calls (one per function)
    - Some TRACE_RETURN calls (at function returns)
    """
    func_files = list(RECOMPILED_FUNCS.glob("funcs_*.c"))

    if not func_files:
        import pytest
        pytest.skip("No funcs_*.c files found - run N64Recomp first")

    total_entry = 0
    total_return = 0

    for func_file in func_files:
        content = func_file.read_text()
        total_entry += content.count('TRACE_ENTRY()')
        total_return += content.count('TRACE_RETURN()')

    # We expect at least 1000 trace entries for any reasonable game
    assert total_entry > 1000, (
        f"Only {total_entry} TRACE_ENTRY() calls found.\n"
        f"Expected thousands for HM64. Re-run N64Recomp with trace_mode = true."
    )

    print(f"[PASS] Trace counts look reasonable:")
    print(f"       TRACE_ENTRY: {total_entry}")
    print(f"       TRACE_RETURN: {total_return}")


def run_all_tests():
    """Run all trace tests."""
    print("=" * 60)
    print("Trace Macro Tests")
    print("=" * 60)
    print(f"RecompiledFuncs: {RECOMPILED_FUNCS}")
    print(f"Trace Header: {TRACE_HEADER}")
    print("-" * 60)

    tests = [
        test_trace_header_exists,
        test_trace_header_defaults_off,
        test_cmake_trace_option_defaults_off,
        test_recompiled_funcs_include_trace,
        test_recompiled_funcs_have_trace_entry,
        test_recompiled_funcs_have_trace_return,
        test_trace_count_reasonable,
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
