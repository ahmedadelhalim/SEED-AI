"""
Detailed PE Architecture, Import, and Dependency Inspector (Corrected Magic)
Inspects headers, machine architecture, import directories, and file sizes.
"""

import sys
import struct
from pathlib import Path

def inspect_dll(dll_path):
    print(f"\n==================================================")
    print(f"FILE: {dll_path.name}")
    print(f"PATH: {dll_path}")
    print(f"SIZE: {dll_path.stat().st_size:,} bytes")
    
    data = dll_path.read_bytes()
    if data[:2] != b"MZ":
        print("ERROR: Not a PE file (Missing MZ header)")
        return

    pe_offset = struct.unpack("<I", data[0x3C:0x3C+4])[0]
    if data[pe_offset:pe_offset+4] != b"PE\0\0":
        print("ERROR: Invalid PE signature")
        return

    machine = struct.unpack("<H", data[pe_offset+4:pe_offset+6])[0]
    if machine == 0x8664:
        arch = "x64 (AMD64)"
    elif machine == 0x14C:
        arch = "x86 (I386)"
    else:
        arch = f"Unknown (0x{machine:X})"
    print(f"Architecture: {arch}")

    num_sections = struct.unpack("<H", data[pe_offset+6:pe_offset+8])[0]
    opt_header_size = struct.unpack("<H", data[pe_offset+20:pe_offset+22])[0]
    opt_header_offset = pe_offset + 24
    
    magic = struct.unpack("<H", data[opt_header_offset:opt_header_offset+2])[0]
    is_64 = (magic == 0x20B) # IMAGE_NT_OPTIONAL_HDR64_MAGIC
    print(f"PE Format: {'PE32+' if is_64 else 'PE32'} (Magic: 0x{magic:X})")

    # Data directories: Import Table is the 2nd entry (index 1) in Optional Header Data Directories
    # For PE32+ (64-bit), Data Directories start at opt_header_offset + 112
    # For PE32 (32-bit), Data Directories start at opt_header_offset + 96
    dir_table_offset = opt_header_offset + (112 if is_64 else 96)
    sections_offset = opt_header_offset + opt_header_size

    sections = []
    for i in range(num_sections):
        s_off = sections_offset + i * 40
        if s_off + 40 > len(data):
            break
        name = data[s_off:s_off+8].rstrip(b'\0').decode('utf-8', errors='ignore')
        v_size, v_addr, raw_size, raw_ptr = struct.unpack("<IIII", data[s_off+8:s_off+24])
        sections.append((name, v_addr, v_size, raw_ptr, raw_size))

    def rva_to_offset(rva):
        for name, v_addr, v_size, raw_ptr, raw_size in sections:
            if v_addr <= rva < v_addr + v_size:
                return rva - v_addr + raw_ptr
        return 0

    if dir_table_offset + 16 <= len(data):
        import_rva, import_size = struct.unpack("<II", data[dir_table_offset+8:dir_table_offset+16])
        print(f"Import Table RVA: 0x{import_rva:X}, Size: {import_size}")
        
        import_off = rva_to_offset(import_rva)
        if import_off:
            print("Imported DLL Dependencies:")
            curr = import_off
            while curr + 20 <= len(data):
                orig_first_thunk, time_date, forwarder, name_rva, first_thunk = struct.unpack("<IIIII", data[curr:curr+20])
                if name_rva == 0:
                    break
                name_off = rva_to_offset(name_rva)
                if name_off:
                    end_null = data.find(b'\0', name_off)
                    dll_name = data[name_off:end_null].decode('utf-8', errors='ignore')
                    print(f"   -> {dll_name}")
                curr += 20
        else:
            print("Import Table RVA could not be mapped to file offset.")


if __name__ == "__main__":
    bin_dir = Path("d:/SEED-AI/bin")
    for dll in sorted(bin_dir.glob("*.dll")):
        inspect_dll(dll)
