"""
Robust PE Import & Export Table Inspector using pure Python
Parses PE headers, sections, import table, and export table from ggml.dll and llama.dll.
"""

import struct
from pathlib import Path

def inspect_pe(dll_path):
    print(f"\n================ INSPECTING {dll_path.name} ================")
    data = dll_path.read_bytes()
    if data[:2] != b"MZ":
        print("Not a valid PE file (missing MZ)")
        return

    pe_offset = struct.unpack("<I", data[0x3C:0x3C+4])[0]
    if data[pe_offset:pe_offset+4] != b"PE\0\0":
        print("Not a valid PE file (missing PE signature)")
        return

    # Machine type at pe_offset + 4 (0x14C = i386, 0x8664 = AMD64)
    machine = struct.unpack("<H", data[pe_offset+4:pe_offset+6])[0]
    arch = "x64 (AMD64)" if machine == 0x8664 else ("x86 (I386)" if machine == 0x14C else f"Unknown (0x{machine:X})")
    print(f"Architecture: {arch}")

    num_sections = struct.unpack("<H", data[pe_offset+6:pe_offset+8])[0]
    opt_header_size = struct.unpack("<H", data[pe_offset+20:pe_offset+22])[0]
    opt_header_offset = pe_offset + 24
    
    magic = struct.unpack("<H", data[opt_header_offset:opt_header_offset+2])[0]
    is_64 = (magic == 0x203)
    
    # Data directories are at opt_header_offset + 112 (64-bit) or + 96 (32-bit)
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

    # 1. Imports (Directory entry 1)
    if dir_table_offset + 16 <= len(data):
        import_rva, import_size = struct.unpack("<II", data[dir_table_offset+8:dir_table_offset+16])
        if import_rva > 0:
            print("\n[Direct Imported DLLs]:")
            import_off = rva_to_offset(import_rva)
            if import_off:
                curr = import_off
                while curr + 20 <= len(data):
                    orig_first_thunk, time_date, forwarder, name_rva, first_thunk = struct.unpack("<IIIII", data[curr:curr+20])
                    if name_rva == 0:
                        break
                    name_off = rva_to_offset(name_rva)
                    if name_off:
                        end_null = data.find(b'\0', name_off)
                        dll_name = data[name_off:end_null].decode('utf-8', errors='ignore')
                        print(f"  - {dll_name}")
                    curr += 20

    # 2. Exports (Directory entry 0)
    if dir_table_offset + 8 <= len(data):
        export_rva, export_size = struct.unpack("<II", data[dir_table_offset:dir_table_offset+8])
        if export_rva > 0:
            print("\n[Exported Symbols (sample)]")
            export_off = rva_to_offset(export_rva)
            if export_off and export_off + 40 <= len(data):
                num_functions = struct.unpack("<I", data[export_off+20:export_off+24])[0]
                num_names = struct.unpack("<I", data[export_off+24:export_off+28])[0]
                names_rva = struct.unpack("<I", data[export_off+32:export_off+36])[0]
                names_off = rva_to_offset(names_rva)
                if names_off:
                    print(f"  Total Exported Functions: {num_functions}, Named: {num_names}")
                    count = 0
                    for i in range(min(num_names, 40)):
                        n_rva = struct.unpack("<I", data[names_off + i*4 : names_off + i*4 + 4])[0]
                        n_off = rva_to_offset(n_rva)
                        if n_off:
                            end_null = data.find(b'\0', n_off)
                            sym_name = data[n_off:end_null].decode('utf-8', errors='ignore')
                            print(f"    * {sym_name}")
                            count += 1


if __name__ == "__main__":
    bin_dir = Path("d:/SEED-AI/bin")
    inspect_pe(bin_dir / "ggml.dll")
    inspect_pe(bin_dir / "llama.dll")
