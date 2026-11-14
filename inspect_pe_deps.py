"""
PE Dependency & Export Inspection Script for llama.dll and ggml.dll
Inspects DLL imports, required runtime libraries, and exported symbols.
"""

import os
import ctypes
from pathlib import Path

def inspect_dlls():
    bin_dir = Path("d:/SEED-AI/bin").resolve()
    ggml_path = bin_dir / "ggml.dll"
    llama_path = bin_dir / "llama.dll"
    
    print(f"Inspecting bin_dir: {bin_dir}")
    print(f"ggml.dll exists: {ggml_path.exists()} ({ggml_path.stat().st_size if ggml_path.exists() else 0} bytes)")
    print(f"llama.dll exists: {llama_path.exists()} ({llama_path.stat().st_size if llama_path.exists() else 0} bytes)")

    # Test loading with os.add_dll_directory
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(bin_dir))
    
    try:
        # Load ggml first
        ggml_lib = ctypes.CDLL(str(ggml_path))
        print("[SUCCESS] Loaded ggml.dll successfully!")
    except Exception as e:
        print("[FAIL] Could not load ggml.dll:", e)

    try:
        llama_lib = ctypes.CDLL(str(llama_path))
        print("[SUCCESS] Loaded llama.dll successfully!")
        
        # Check exports
        symbols = [
            "llama_backend_init", "llama_model_default_params",
            "llama_load_model_from_file", "llama_new_context_with_model",
            "llama_tokenize", "llama_decode", "llama_free",
            "llama_free_model", "llama_backend_free"
        ]
        for sym in symbols:
            exists = hasattr(llama_lib, sym)
            print(f"  Export {sym}: {exists}")
    except Exception as e:
        print("[FAIL] Could not load llama.dll:", e)


if __name__ == "__main__":
    inspect_dlls()
