#!/usr/bin/env python3
"""
Create a minimal Altium .SchLib file that reproduces the KiCad bug:
ReadProperties() incorrectly strips trailing null byte from binary PinFrac records.

The bug occurs when compressed PinFrac data happens to end with 0x00,
which ReadProperties() mistakes for a string null terminator and strips,
causing ReadFullPascalString() to throw std::out_of_range.

This script extracts ATtiny13 from IC.SchLib and creates a minimal
single-component .SchLib for testing. It can also create a fully
synthetic test file without needing IC.SchLib.

Usage:
    python3 create_minimal_test.py [IC.SchLib]

If IC.SchLib is provided, extracts ATtiny13 from it.
Otherwise, creates a synthetic component with crafted PinFrac data.
"""

import struct
import sys
import os

# ── CFB constants ──
SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 4096
DIR_ENTRY_SIZE = 128
NOSTREAM = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FATSECT = 0xFFFFFFFD
CFB_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


def encode_utf16(name):
    """Encode name to UTF-16LE, padded to 64 bytes."""
    encoded = name.encode('utf-16-le') + b'\x00\x00'  # null terminator
    byte_len = len(encoded)
    return encoded.ljust(64, b'\x00'), byte_len


def make_dir_entry(name, obj_type, color=1, left=NOSTREAM, right=NOSTREAM,
                   child=NOSTREAM, start=0, size=0):
    """Create a 128-byte directory entry."""
    name_bytes, name_len = encode_utf16(name)
    entry = bytearray(128)
    entry[0:64] = name_bytes
    struct.pack_into('<H', entry, 64, name_len)        # name size in bytes
    entry[66] = obj_type                                 # type
    entry[67] = color                                    # color (1=black)
    struct.pack_into('<I', entry, 68, left)              # left sibling
    struct.pack_into('<I', entry, 72, right)             # right sibling
    struct.pack_into('<I', entry, 76, child)             # child
    # CLSID (16 bytes at 80) = 0
    # State bits (4 bytes at 96) = 0
    # Timestamps (16 bytes at 100) = 0
    struct.pack_into('<I', entry, 116, start)            # start sector
    struct.pack_into('<I', entry, 120, size)             # size (low 32)
    struct.pack_into('<I', entry, 124, 0)                # size (high 32)
    return bytes(entry)


def pad_to(data, boundary):
    """Pad data to next boundary."""
    remainder = len(data) % boundary
    if remainder:
        data += b'\x00' * (boundary - remainder)
    return data


def create_minimal_schlib(data_stream, pinfrac_stream, component_name, output_path):
    """
    Create a minimal CFB v3 .SchLib file with one component.
    
    Layout:
      Header (512 bytes)
      Sector 0: FAT
      Sector 1: Directory (4 entries)
      Sector 2: Mini-FAT
      Sector 3+: Mini-stream data (Root Entry stream)
    """
    # ── Build mini-stream (concatenation of all small streams) ──
    mini_stream = bytearray()

    # Data stream → mini-sectors starting at 0
    data_start_minisec = 0
    mini_stream += data_stream
    mini_stream = bytearray(pad_to(bytes(mini_stream), MINI_SECTOR_SIZE))
    data_minisecs = (len(data_stream) + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE

    # PinFrac stream → mini-sectors starting after Data
    pinfrac_start_minisec = data_minisecs
    mini_stream += pinfrac_stream
    mini_stream = bytearray(pad_to(bytes(mini_stream), MINI_SECTOR_SIZE))
    pinfrac_minisecs = (len(pinfrac_stream) + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE

    total_minisecs = data_minisecs + pinfrac_minisecs

    # Pad mini-stream to sector boundary (it's stored as Root Entry's data)
    mini_stream_padded = pad_to(bytes(mini_stream), SECTOR_SIZE)
    root_stream_sectors = len(mini_stream_padded) // SECTOR_SIZE

    # ── Build Mini-FAT ──
    mini_fat = bytearray()
    # Data chain: 0 → 1 → ... → (data_minisecs-1) → ENDOFCHAIN
    for i in range(data_minisecs):
        if i < data_minisecs - 1:
            struct.pack_into('<I', mini_fat := mini_fat + b'\x00\x00\x00\x00', len(mini_fat) - 4, i + 1)
        else:
            struct.pack_into('<I', mini_fat := mini_fat + b'\x00\x00\x00\x00', len(mini_fat) - 4, ENDOFCHAIN)
    # PinFrac chain
    for i in range(pinfrac_minisecs):
        sec = pinfrac_start_minisec + i
        if i < pinfrac_minisecs - 1:
            struct.pack_into('<I', mini_fat := mini_fat + b'\x00\x00\x00\x00', len(mini_fat) - 4, sec + 1)
        else:
            struct.pack_into('<I', mini_fat := mini_fat + b'\x00\x00\x00\x00', len(mini_fat) - 4, ENDOFCHAIN)
    # Fill rest of sector with FREESECT
    while len(mini_fat) < SECTOR_SIZE:
        mini_fat += struct.pack('<I', FREESECT)

    # ── Sector layout ──
    # Sector 0: FAT
    # Sector 1: Directory
    # Sector 2: Mini-FAT
    # Sector 3..3+N-1: Root Entry stream (mini-stream container)
    root_stream_start = 3
    total_sectors = 3 + root_stream_sectors

    # ── Build FAT ──
    fat = bytearray()
    fat += struct.pack('<I', FATSECT)       # Sector 0 = FAT
    fat += struct.pack('<I', ENDOFCHAIN)    # Sector 1 = Directory (single sector)
    fat += struct.pack('<I', ENDOFCHAIN)    # Sector 2 = Mini-FAT (single sector)
    # Root Entry stream chain: 3 → 4 → ... → ENDOFCHAIN
    for i in range(root_stream_sectors):
        sec = root_stream_start + i
        if i < root_stream_sectors - 1:
            fat += struct.pack('<I', sec + 1)
        else:
            fat += struct.pack('<I', ENDOFCHAIN)
    # Fill rest with FREESECT
    while len(fat) < SECTOR_SIZE:
        fat += struct.pack('<I', FREESECT)

    # ── Build Directory ──
    # Entry 0: Root Entry (storage, child=1, stream data = mini-stream)
    # Entry 1: component_name (storage, child=2)
    # Entry 2: "Data" (stream, right_sibling=3)
    # Entry 3: "PinFrac" (stream)
    directory = bytearray()
    directory += make_dir_entry("Root Entry", obj_type=5, color=1,
                                child=1, start=root_stream_start,
                                size=len(mini_stream))
    directory += make_dir_entry(component_name, obj_type=1, color=1,
                                child=2)
    directory += make_dir_entry("Data", obj_type=2, color=1,
                                right=3,
                                start=data_start_minisec,
                                size=len(data_stream))
    directory += make_dir_entry("PinFrac", obj_type=2, color=0,  # red node
                                start=pinfrac_start_minisec,
                                size=len(pinfrac_stream))
    directory = pad_to(bytes(directory), SECTOR_SIZE)

    # ── Build Header ──
    header = bytearray(SECTOR_SIZE)
    header[0:8] = CFB_MAGIC
    # CLSID = 0 (16 bytes at 8)
    struct.pack_into('<H', header, 24, 0x003E)     # minor version
    struct.pack_into('<H', header, 26, 0x0003)     # major version (v3)
    struct.pack_into('<H', header, 28, 0xFFFE)     # byte order (LE)
    struct.pack_into('<H', header, 30, 9)          # sector size power (2^9=512)
    struct.pack_into('<H', header, 32, 6)          # mini sector size power (2^6=64)
    # reserved 6 bytes at 34
    struct.pack_into('<I', header, 40, 0)          # total dir sectors (must be 0 for v3)
    struct.pack_into('<I', header, 44, 1)          # total FAT sectors
    struct.pack_into('<I', header, 48, 1)          # first directory sector
    struct.pack_into('<I', header, 52, 0)          # transaction signature
    struct.pack_into('<I', header, 56, MINI_STREAM_CUTOFF)  # mini stream cutoff
    struct.pack_into('<I', header, 60, 2)          # first mini FAT sector
    struct.pack_into('<I', header, 64, 1)          # total mini FAT sectors
    struct.pack_into('<I', header, 68, ENDOFCHAIN) # first DIFAT sector (none)
    struct.pack_into('<I', header, 72, 0)          # total DIFAT sectors
    # DIFAT array: first entry = sector 0 (our FAT)
    struct.pack_into('<I', header, 76, 0)
    # Rest of DIFAT array = FREESECT
    for i in range(1, 109):
        struct.pack_into('<I', header, 76 + i * 4, FREESECT)

    # ── Assemble file ──
    output = bytearray()
    output += header
    output += fat
    output += directory
    output += mini_fat
    output += mini_stream_padded

    with open(output_path, 'wb') as f:
        f.write(output)

    print(f"Created {output_path} ({len(output)} bytes)")
    print(f"  Component: {component_name}")
    print(f"  Data stream: {len(data_stream)} bytes ({data_minisecs} mini-sectors)")
    print(f"  PinFrac stream: {len(pinfrac_stream)} bytes ({pinfrac_minisecs} mini-sectors)")
    print(f"  Total sectors: {total_sectors}")


def create_synthetic_data():
    """
    Create synthetic but valid Data and PinFrac streams that trigger the bug.
    No dependency on IC.SchLib.
    """
    import zlib

    # ── Data stream: COMPONENT record + 2 PIN records ──
    data = bytearray()

    # Record 0: COMPONENT (text format)
    comp_props = (
        "|RECORD=1"
        "|LibReference=TestComp"
        "|PartCount=2"
        "|DisplayModeCount=1"
        "|IndexInSheet=-1"
        "|OwnerPartId=-1"
        "|CurrentPartId=1"
        "|LibraryPath=*"
        "|SourceLibraryName=test.SchLib"
        "|TargetFileName=*"
        "|Description=Test component for bug reproduction"
        "|ComponentDescription=Test"
        "|"
    )
    comp_bytes = comp_props.encode('latin-1') + b'\x00'
    data += struct.pack('<I', len(comp_bytes))  # length, no binary flag
    data += comp_bytes

    # Records 1-2: PIN records (binary format)
    for pin_idx in range(2):
        pin_data = bytearray()
        pin_data += struct.pack('<i', 2)           # RECORD=2 (PIN)
        pin_data += struct.pack('B', 0)            # unknown
        pin_data += struct.pack('<h', 1)           # ownerPartId
        pin_data += struct.pack('B', 0)            # displayMode
        pin_data += struct.pack('B', 0)            # innerEdge
        pin_data += struct.pack('B', 0)            # outerEdge
        pin_data += struct.pack('B', 0)            # inner
        pin_data += struct.pack('B', 0)            # outer
        # TEXT (ShortPascalString)
        text = f"P{pin_idx+1}".encode('latin-1')
        pin_data += struct.pack('B', len(text)) + text
        pin_data += struct.pack('B', 0)            # unknown
        pin_data += struct.pack('B', 1)            # electrical (passive)
        pin_data += struct.pack('B', 0x11)         # pinConglomerate
        pin_data += struct.pack('<h', 20)          # pinLength
        pin_data += struct.pack('<h', -30 if pin_idx == 0 else 30)  # locationX
        pin_data += struct.pack('<h', 0)           # locationY
        pin_data += struct.pack('<i', 0)           # color
        # NAME (ShortPascalString)
        name = f"PIN{pin_idx+1}".encode('latin-1')
        pin_data += struct.pack('B', len(name)) + name
        # DESIGNATOR (ShortPascalString)
        des = f"{pin_idx+1}".encode('latin-1')
        pin_data += struct.pack('B', len(des)) + des
        # SWAPIDGROUP (ShortPascalString)
        pin_data += struct.pack('B', 0)
        # partSeq (ShortPascalString) — format: "part|&|seq"
        seq = f"1|&|0".encode('latin-1')
        pin_data += struct.pack('B', len(seq)) + seq

        pin_bytes = bytes(pin_data) + b'\x00'
        # Set binary flag (MSB of length)
        data += struct.pack('<I', len(pin_bytes) | 0x01000000)
        data += pin_bytes

    # ── PinFrac stream ──
    pinfrac = bytearray()

    # Record 0: Header (text format)
    hdr = "|HEADER=PinFrac|Weight=2|"
    hdr_bytes = hdr.encode('latin-1') + b'\x00'
    pinfrac += struct.pack('<I', len(hdr_bytes))
    pinfrac += hdr_bytes

    # Records 1-2: PinFrac entries (binary, compressed)
    for pin_idx in range(2):
        frac_data = struct.pack('<iii', 0, 0, 68504)  # x_frac, y_frac, len_frac

        if pin_idx == 1:
            # CRAFT the zlib data to end with 0x00 — this triggers the bug!
            # We need zlib.compress(frac_data) to end with 0x00.
            # If it doesn't naturally, we pad the input slightly.
            # Actually, let's just find input that compresses to end with 0x00.
            compressed = zlib.compress(frac_data)
            if compressed[-1] != 0x00:
                # Try different y_frac values until we get zlib ending with 0x00
                for y in range(-100000, 100000):
                    test_data = struct.pack('<iii', 0, y, 68504)
                    c = zlib.compress(test_data)
                    if c[-1] == 0x00:
                        frac_data = test_data
                        compressed = c
                        print(f"  Found y_frac={y} that produces zlib ending with 0x00")
                        break
                else:
                    # Fallback: try different compression levels
                    for level in range(1, 10):
                        c = zlib.compress(frac_data, level)
                        if c[-1] == 0x00:
                            compressed = c
                            print(f"  Found compression level {level} ending with 0x00")
                            break
        else:
            compressed = zlib.compress(frac_data)

        # Build compressed record: 0xD0 + ShortPascalString(pin_idx) + FullPascalString(zlib)
        rec = bytearray()
        rec += b'\xd0'
        idx_str = str(pin_idx).encode('ascii')
        rec += struct.pack('B', len(idx_str)) + idx_str
        rec += struct.pack('<I', len(compressed)) + compressed

        rec_bytes = bytes(rec) + b'\x00'  # trailing null byte
        pinfrac += struct.pack('<I', len(rec_bytes) | 0x01000000)
        pinfrac += rec_bytes

    print(f"  Last PinFrac record ends with: 0x{pinfrac[-2]:02x} 0x{pinfrac[-1]:02x}")

    return bytes(data), bytes(pinfrac)


def extract_from_schlib(schlib_path):
    """Extract ATtiny13 Data and PinFrac from IC.SchLib."""
    import olefile
    ole = olefile.OleFileIO(schlib_path)
    data = ole.openstream(['ATtiny13', 'Data']).read()
    pinfrac = ole.openstream(['ATtiny13', 'PinFrac']).read()
    ole.close()
    return data, pinfrac


def main():
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'test_bug_nullbyte.SchLib')

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        print(f"Extracting ATtiny13 from {sys.argv[1]}...")
        data_stream, pinfrac_stream = extract_from_schlib(sys.argv[1])
        component_name = "ATtiny13"
    else:
        print("Creating synthetic test component...")
        data_stream, pinfrac_stream = create_synthetic_data()
        component_name = "TestComp"

    create_minimal_schlib(data_stream, pinfrac_stream, component_name, output_path)

    # Verify the file is readable
    try:
        import olefile
        ole = olefile.OleFileIO(output_path)
        entries = ole.listdir()
        print(f"\nVerification (olefile):")
        for e in entries:
            stream = ole.openstream(e) if ole.get_type(e) != 1 else None
            size = len(stream.read()) if stream else 0
            print(f"  {'/'.join(e)}: {size} bytes")
        ole.close()
        print("OK — file is valid OLE")
    except Exception as e:
        print(f"WARNING: olefile verification failed: {e}")

    print(f"\nTo reproduce the bug:")
    print(f"  kicad-cli sym upgrade {output_path} -o /tmp/test_output.kicad_sym --force")


if __name__ == '__main__':
    main()
