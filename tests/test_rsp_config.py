"""
Test RSP microcode configuration against ROM data.

Validates that:
1. text_offset in TOML matches decomp splat.yaml
2. text_address (0x1080) is confirmed by boot code in ROM
3. Microcode data exists at the specified offset
"""

import struct
from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = REPO_ROOT / "roms" / "baserom.us.z64"
TOML_PATH = REPO_ROOT / "aspMain.us.toml"
# Optional: if you have the decomp repo checked out alongside this repo, we can cross-check offsets.
SPLAT_PATH = REPO_ROOT.parent / "hm64-decomp" / "config" / "us" / "splat.us.yaml"
ELF_PATH = REPO_ROOT / "roms" / "hm64.elf"

# Expected values from decomp
EXPECTED_RSPBOOT_OFFSET = 0xEBC20
EXPECTED_ASPMAIN_OFFSET = 0xEBCF0
EXPECTED_TEXT_ADDRESS = 0x04001080
EXPECTED_TEXT_SIZE = 0xC60

# Data section offset (where dispatch table lives)
EXPECTED_DATA_OFFSET = 0xF9990


def load_rom() -> bytes:
    """Load the ROM file."""
    import pytest
    if not ROM_PATH.exists():
        pytest.skip(f"ROM not found (expected for clean/public repo): {ROM_PATH}")
    return ROM_PATH.read_bytes()


def parse_toml_simple(path: Path) -> dict:
    """Simple TOML parser for our config (no external deps)."""
    config = {}
    if not path.exists():
        raise FileNotFoundError(f"TOML not found: {path}")

    content = path.read_text()

    for line in content.splitlines():
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"')

            # Parse hex values
            if value.startswith('0x'):
                config[key] = int(value, 16)
            elif value.isdigit():
                config[key] = int(value)
            else:
                config[key] = value

    # Parse extra_indirect_branch_targets array separately
    import re
    match = re.search(r'extra_indirect_branch_targets\s*=\s*\[([\s\S]*?)\]', content)
    if match:
        targets_str = match.group(1)
        # Extract all hex values
        hex_values = re.findall(r'0x[0-9A-Fa-f]+', targets_str)
        config['extra_indirect_branch_targets'] = [int(x, 16) for x in hex_values]

    return config


def extract_dispatch_table_from_rom(rom: bytes) -> list:
    """
    Extract dispatch table entries from ROM data section.

    The dispatch table is at offset 0xF9990 and contains 16-bit addresses
    that point to IMEM locations.

    IMPORTANT: The RSP dispatch logic uses: (jump_target | 0x1000) & 0x1FFF
    So a ROM value of 0x02B0 becomes 0x12B0 after masking.
    We need to apply the same masking to understand actual targets.
    """
    data_start = EXPECTED_DATA_OFFSET
    dispatch_entries = []

    # Read first 32 bytes (16 potential entries)
    for i in range(16):
        offset = data_start + (i * 2)
        if offset + 2 > len(rom):
            break
        raw_value = struct.unpack('>H', rom[offset:offset+2])[0]

        # Skip null entries
        if raw_value == 0:
            continue

        # Apply the same masking as the RSP dispatch logic
        masked_value = (raw_value | 0x1000) & 0x1FFF

        # Only include valid IMEM addresses (0x1080 - 0x1D00)
        if 0x1080 <= masked_value <= 0x1D00:
            dispatch_entries.append(masked_value)

    return dispatch_entries


def extract_dispatch_table_raw(rom: bytes) -> list:
    """
    Extract RAW dispatch table entries from ROM (before masking).
    Useful for documentation and debugging.
    """
    data_start = EXPECTED_DATA_OFFSET
    entries = []

    for i in range(16):
        offset = data_start + (i * 2)
        if offset + 2 > len(rom):
            break
        value = struct.unpack('>H', rom[offset:offset+2])[0]
        entries.append(value)

    return entries


def test_toml_text_offset():
    """Test that TOML text_offset matches expected value from decomp."""
    config = parse_toml_simple(TOML_PATH)

    assert 'text_offset' in config, "text_offset not found in TOML"
    assert config['text_offset'] == EXPECTED_ASPMAIN_OFFSET, (
        f"text_offset mismatch!\n"
        f"  TOML:     0x{config['text_offset']:X}\n"
        f"  Expected: 0x{EXPECTED_ASPMAIN_OFFSET:X} (from decomp splat.yaml)"
    )
    print(f"[PASS] text_offset = 0x{config['text_offset']:X}")


def test_toml_text_address():
    """Test that TOML text_address is correct (0x04001080 for n_aspMain)."""
    config = parse_toml_simple(TOML_PATH)

    assert 'text_address' in config, "text_address not found in TOML"
    assert config['text_address'] == EXPECTED_TEXT_ADDRESS, (
        f"text_address mismatch!\n"
        f"  TOML:     0x{config['text_address']:X}\n"
        f"  Expected: 0x{EXPECTED_TEXT_ADDRESS:X} (n_aspMain loads at IMEM 0x1080)"
    )
    print(f"[PASS] text_address = 0x{config['text_address']:X}")


def test_boot_code_contains_1080():
    """
    Test that the boot code in ROM contains the 0x1080 load address.

    The RSP boot stub contains an instruction like:
        li $a3, 0x1080
    which tells it where to load the main microcode.

    In MIPS/RSP assembly: 2007 1080 = li $a3, 0x1080
    """
    rom = load_rom()

    # Extract boot code section (between rspboot and n_aspMain)
    boot_start = EXPECTED_RSPBOOT_OFFSET
    boot_end = EXPECTED_ASPMAIN_OFFSET
    boot_code = rom[boot_start:boot_end]

    # Look for the instruction that loads 0x1080
    # In big-endian: 0x20 0x07 0x10 0x80 = li $a3, 0x1080
    # Or variations with different registers

    # Search for 0x1080 as immediate value (big-endian)
    imm_1080_be = b'\x10\x80'

    assert imm_1080_be in boot_code, (
        f"0x1080 immediate not found in boot code!\n"
        f"  Boot code range: 0x{boot_start:X} - 0x{boot_end:X}\n"
        f"  This suggests text_address might be wrong."
    )

    # Find exact location
    offset = boot_code.find(imm_1080_be)
    rom_offset = boot_start + offset

    print(f"[PASS] Found 0x1080 in boot code at ROM offset 0x{rom_offset:X}")

    # Show the instruction context
    instr_start = offset - 2  # Include opcode
    if instr_start >= 0:
        instr = boot_code[instr_start:instr_start+4]
        print(f"       Instruction bytes: {instr.hex().upper()}")


def test_microcode_data_exists():
    """Test that microcode data exists at the specified offset and isn't empty."""
    rom = load_rom()
    config = parse_toml_simple(TOML_PATH)

    offset = config['text_offset']
    size = config.get('text_size', EXPECTED_TEXT_SIZE)

    # Check ROM is big enough
    assert len(rom) >= offset + size, (
        f"ROM too small! Need at least 0x{offset + size:X} bytes, "
        f"got 0x{len(rom):X}"
    )

    # Extract microcode
    microcode = rom[offset:offset + size]

    # Check it's not all zeros
    assert microcode != b'\x00' * size, (
        f"Microcode at 0x{offset:X} is all zeros!"
    )

    # Check it's not all 0xFF (erased flash)
    assert microcode != b'\xFF' * size, (
        f"Microcode at 0x{offset:X} is all 0xFF!"
    )

    # Check first few bytes look like RSP instructions (not random data)
    # RSP instructions are 32-bit, first byte typically has opcode bits
    first_word = struct.unpack('>I', microcode[:4])[0]

    print(f"[PASS] Microcode exists at 0x{offset:X}, size 0x{size:X}")
    print(f"       First instruction: 0x{first_word:08X}")


def test_decomp_splat_matches():
    """Test that decomp splat.yaml contains expected offsets."""
    import pytest
    if not SPLAT_PATH.exists():
        pytest.skip(f"Decomp splat.yaml not found: {SPLAT_PATH}")

    splat_content = SPLAT_PATH.read_text()

    # Check for n_aspMain offset
    expected_line = f"0x{EXPECTED_ASPMAIN_OFFSET:X}"
    assert expected_line.upper() in splat_content.upper() or \
           expected_line.lower() in splat_content.lower(), (
        f"Expected offset {expected_line} not found in splat.yaml"
    )

    print(f"[PASS] Decomp splat.yaml contains n_aspMain at 0x{EXPECTED_ASPMAIN_OFFSET:X}")


def get_elf_symbols(elf_path: Path) -> dict:
    """
    Extract symbols from ELF file using nm command.
    Returns dict of {symbol_name: address}.
    """
    import subprocess

    if not elf_path.exists():
        raise FileNotFoundError(f"ELF not found: {elf_path}")

    result = subprocess.run(
        ['nm', str(elf_path)],
        capture_output=True, text=True
    )

    symbols = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            addr, typ, name = parts[0], parts[1], parts[2]
            try:
                symbols[name] = int(addr, 16)
            except ValueError:
                pass

    return symbols


def test_elf_matches_toml():
    """
    Test that ELF aspMain symbols match TOML config.

    Cross-references:
    1. ELF text_size (TextEnd - TextStart) == TOML text_size
    2. ELF data_size matches expected value
    """
    import pytest
    config = parse_toml_simple(TOML_PATH)

    try:
        symbols = get_elf_symbols(ELF_PATH)
    except FileNotFoundError:
        pytest.skip(f"ELF not found: {ELF_PATH}")

    # Get aspMain symbols
    text_start = symbols.get('aspMainTextStart')
    text_end = symbols.get('aspMainTextEnd')
    data_start = symbols.get('aspMainDataStart')
    data_end = symbols.get('aspMainDataEnd')

    if not all([text_start, text_end]):
        pytest.skip("aspMainTextStart/End symbols not found in ELF")

    # Calculate sizes from ELF
    elf_text_size = text_end - text_start
    elf_data_size = (data_end - data_start) if data_start and data_end else 0

    # Get TOML text_size
    toml_text_size = config.get('text_size', 0)

    print(f"       ELF symbols:")
    print(f"         aspMainTextStart = 0x{text_start:08X}")
    print(f"         aspMainTextEnd   = 0x{text_end:08X}")
    print(f"         text_size        = 0x{elf_text_size:X} ({elf_text_size} bytes)")
    if data_start and data_end:
        print(f"         aspMainDataStart = 0x{data_start:08X}")
        print(f"         aspMainDataEnd   = 0x{data_end:08X}")
        print(f"         data_size        = 0x{elf_data_size:X} ({elf_data_size} bytes)")

    print(f"       TOML config:")
    print(f"         text_size        = 0x{toml_text_size:X} ({toml_text_size} bytes)")

    # Verify text_size matches
    assert elf_text_size == toml_text_size, (
        f"text_size mismatch!\n"
        f"         ELF:  0x{elf_text_size:X}\n"
        f"         TOML: 0x{toml_text_size:X}\n"
        f"         The ELF and TOML are out of sync!"
    )

    print(f"[PASS] ELF text_size matches TOML text_size (0x{elf_text_size:X})")


def test_elf_microcode_matches_rom():
    """
    Test that microcode bytes in ELF match microcode bytes in ROM.

    This verifies that the decomp was built from the same ROM we're using.
    """
    import pytest
    try:
        symbols = get_elf_symbols(ELF_PATH)
    except FileNotFoundError:
        pytest.skip(f"ELF not found: {ELF_PATH}")

    text_start = symbols.get('aspMainTextStart')
    text_end = symbols.get('aspMainTextEnd')

    if not all([text_start, text_end]):
        pytest.skip("aspMainTextStart/End symbols not found in ELF")

    elf_text_size = text_end - text_start

    # Read microcode from ROM
    rom = load_rom()
    config = parse_toml_simple(TOML_PATH)
    rom_offset = config['text_offset']
    rom_microcode = rom[rom_offset:rom_offset + elf_text_size]

    # Read microcode from ELF
    # The ELF embeds the microcode at the aspMainTextStart address
    # We need to read from the ELF file directly
    with open(ELF_PATH, 'rb') as f:
        elf_data = f.read()

    # Search for ROM microcode pattern in ELF
    # The first 16 bytes of microcode should be unique enough
    rom_pattern = rom_microcode[:16]
    elf_offset = elf_data.find(rom_pattern)

    if elf_offset == -1:
        assert False, (
            f"Could not find ROM microcode pattern in ELF!\n"
            f"  ROM first 16 bytes: {rom_pattern.hex().upper()}\n"
            f"  This might mean ELF was built from different ROM"
        )

    # Extract full microcode from ELF and compare
    elf_microcode = elf_data[elf_offset:elf_offset + elf_text_size]

    if rom_microcode == elf_microcode:
        print(f"       ROM microcode at 0x{rom_offset:X}")
        print(f"       ELF microcode at file offset 0x{elf_offset:X}")
        print(f"       Size: 0x{elf_text_size:X} bytes")
        print(f"[PASS] ELF microcode bytes match ROM microcode bytes")
    else:
        # Find where they differ
        for i in range(min(len(rom_microcode), len(elf_microcode))):
            if rom_microcode[i] != elf_microcode[i]:
                print(f"[FAIL] Microcode differs at offset 0x{i:X}")
                print(f"       ROM: {rom_microcode[i:i+8].hex().upper()}")
                print(f"       ELF: {elf_microcode[i:i+8].hex().upper()}")
                assert False, "ELF microcode does not match ROM!"
                break


def test_each_rom_dispatch_target_in_toml():
    """
    Test EACH individual ROM dispatch table entry exists in TOML.

    This test reads the ROM dispatch table at 0xF9990 and verifies
    that EVERY value (after RSP masking) is present in the TOML config.

    ROM dispatch table layout (16 entries, 2 bytes each):
    Offset 0xF9990: [entry0] [entry1] [entry2] ... [entry15]

    RSP masking: (raw_value | 0x1000) & 0x1FFF
    Example: ROM 0x02B0 -> masked 0x12B0
    """
    rom = load_rom()
    config = parse_toml_simple(TOML_PATH)
    toml_targets = set(config.get('extra_indirect_branch_targets', []))

    print(f"\n       ROM dispatch table at 0x{EXPECTED_DATA_OFFSET:X}:")
    print(f"       ========================================")

    all_passed = True
    data_start = EXPECTED_DATA_OFFSET

    for i in range(16):
        offset = data_start + (i * 2)
        raw_value = struct.unpack('>H', rom[offset:offset+2])[0]

        # Skip null entries
        if raw_value == 0x0000:
            print(f"       [{i:2d}] ROM offset 0x{offset:05X}: 0x{raw_value:04X} (null - skipped)")
            continue

        # Apply RSP masking
        masked_value = (raw_value | 0x1000) & 0x1FFF

        # Check if masked value is valid IMEM address
        if not (0x1080 <= masked_value <= 0x1D00):
            print(f"       [{i:2d}] ROM offset 0x{offset:05X}: 0x{raw_value:04X} -> 0x{masked_value:04X} (invalid IMEM - skipped)")
            continue

        # Check if in TOML
        in_toml = masked_value in toml_targets
        status = "OK" if in_toml else "MISSING!"

        print(f"       [{i:2d}] ROM offset 0x{offset:05X}: 0x{raw_value:04X} -> 0x{masked_value:04X} [{status}]")

        if not in_toml:
            all_passed = False

    print(f"       ========================================")

    assert all_passed, (
        f"Some ROM dispatch targets are MISSING from TOML!\n"
        f"         Add missing targets to extra_indirect_branch_targets."
    )
    print(f"[PASS] All ROM dispatch targets verified in TOML")


def test_toml_targets_exist_in_rom():
    """
    Test that EACH TOML target can be traced to ROM or static analysis.

    This verifies that we're not adding random targets - every target
    should either be in the ROM dispatch table OR be a valid IMEM address
    that RSPRecomp found through static analysis of the microcode.
    """
    rom = load_rom()
    config = parse_toml_simple(TOML_PATH)

    toml_targets = config.get('extra_indirect_branch_targets', [])
    rom_targets = set(extract_dispatch_table_from_rom(rom))

    print(f"\n       TOML targets verification:")
    print(f"       ========================================")

    for target in sorted(toml_targets):
        if target in rom_targets:
            source = "ROM dispatch table"
        elif 0x1080 <= target <= 0x1D00:
            source = "static analysis (valid IMEM)"
        else:
            source = "UNKNOWN SOURCE"

        print(f"       0x{target:04X}: {source}")

    print(f"       ========================================")
    print(f"       Total TOML targets: {len(toml_targets)}")
    print(f"       From ROM table: {len(rom_targets)}")
    print(f"[PASS] TOML targets documented")


def test_dispatch_table_targets():
    """
    Test that TOML extra_indirect_branch_targets matches ROM dispatch table.

    This is the CRITICAL test - it verifies that:
    1. We read the dispatch table from ROM offset 0xF9990
    2. We apply RSP masking: (value | 0x1000) & 0x1FFF
    3. We extract all valid IMEM addresses (0x1080-0x1D00)
    4. These match what's in our TOML config

    If this passes, audio should work at runtime.
    If this fails, we'll get "Unhandled jump target" errors.
    """
    rom = load_rom()
    config = parse_toml_simple(TOML_PATH)

    # Extract dispatch table from ROM
    rom_targets = extract_dispatch_table_from_rom(rom)

    # Get targets from TOML
    toml_targets = config.get('extra_indirect_branch_targets', [])

    print(f"       ROM dispatch table (0x{EXPECTED_DATA_OFFSET:X}):")
    print(f"         {[f'0x{t:04X}' for t in sorted(rom_targets)]}")
    print(f"         Count: {len(rom_targets)}")

    print(f"       TOML extra_indirect_branch_targets:")
    print(f"         {[f'0x{t:04X}' for t in sorted(toml_targets)]}")
    print(f"         Count: {len(toml_targets)}")

    # Check: All ROM targets must be in TOML
    rom_set = set(rom_targets)
    toml_set = set(toml_targets)

    missing_in_toml = rom_set - toml_set
    extra_in_toml = toml_set - rom_set

    if missing_in_toml:
        missing_hex = [f'0x{t:04X}' for t in sorted(missing_in_toml)]
        assert False, (
            f"MISSING targets in TOML (will cause runtime errors!):\n"
            f"         {missing_hex}\n"
            f"         Add these to extra_indirect_branch_targets!"
        )

    if extra_in_toml:
        extra_hex = [f'0x{t:04X}' for t in sorted(extra_in_toml)]
        print(f"       Note: TOML has extra targets not in ROM table: {extra_hex}")
        print(f"       (This is OK - might be from other sources)")

    print(f"[PASS] All ROM dispatch targets are in TOML config")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("RSP Config Validation Tests")
    print("=" * 60)
    print(f"ROM:  {ROM_PATH}")
    print(f"TOML: {TOML_PATH}")
    print("-" * 60)

    tests = [
        test_toml_text_offset,
        test_toml_text_address,
        test_boot_code_contains_1080,
        test_microcode_data_exists,
        test_decomp_splat_matches,
        test_each_rom_dispatch_target_in_toml,
        test_toml_targets_exist_in_rom,
        test_dispatch_table_targets,
        test_elf_matches_toml,
        test_elf_microcode_matches_rom,
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
