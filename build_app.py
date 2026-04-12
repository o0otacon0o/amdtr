import PyInstaller.__main__
import os
import platform
import subprocess
import sys
from pathlib import Path

def ensure_vendor_assets():
    """Ensures that JS/CSS resources are present."""
    vendor_dir = Path(__file__).parent / "resources" / "vendor"
    # Check for one of the critical files
    required_file = vendor_dir / "marked.min.js"
    
    if not required_file.exists():
        print("[*] Vendor assets missing. Running setup_vendor.py...")
        try:
            # Execute setup_vendor.py
            subprocess.run([sys.executable, "setup_vendor.py"], check=True)
            print("[+] Vendor assets downloaded successfully.")
        except Exception as e:
            print(f"[!] Error downloading vendor assets: {e}")
            sys.exit(1)
    else:
        print("[+] Vendor assets already present.")

def build():
    # Ensure that resources are present
    ensure_vendor_assets()
    
    # OS-specific settings
    is_windows = platform.system() == "Windows"
    separator = ";" if is_windows else ":"
    
    # Resource paths (Source:Destination)
    datas = [
        (f"resources{os.sep}*", "resources"),
        (f"themes{os.sep}*.json", "themes"),
    ]
    
    # Arguments for PyInstaller
    args = [
        'main.py',                    # Entry point
        '--name=amdtr',               # App-Name
        '--icon=amdtr-ico.png',       # Icon-File
        '--onefile',                  # Single EXE
        '--windowed',                 # No console
        '--clean',                    # Clear cache
    ]
    
    # Add data paths
    for src, dst in datas:
        args.append(f'--add-data={src}{separator}{dst}')
    
    print(f"[*] Starting build for {platform.system()}...")
    
    PyInstaller.__main__.run(args)
    
    print("\n[+] Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
