import PyInstaller.__main__
import os
import platform
import subprocess
import sys
from pathlib import Path

def ensure_vendor_assets():
    """Stellt sicher, dass die JS/CSS Ressourcen vorhanden sind."""
    vendor_dir = Path(__file__).parent / "resources" / "vendor"
    # Prüfe auf eine der kritischen Dateien
    required_file = vendor_dir / "marked.min.js"
    
    if not required_file.exists():
        print("[*] Vendor assets missing. Running setup_vendor.py...")
        try:
            # Führe setup_vendor.py aus
            subprocess.run([sys.executable, "setup_vendor.py"], check=True)
            print("[+] Vendor assets downloaded successfully.")
        except Exception as e:
            print(f"[!] Error downloading vendor assets: {e}")
            sys.exit(1)
    else:
        print("[+] Vendor assets already present.")

def build():
    # Sicherstellen, dass Ressourcen da sind
    ensure_vendor_assets()
    
    # OS-Spezifische Einstellungen
    is_windows = platform.system() == "Windows"
    separator = ";" if is_windows else ":"
    
    # Ressourcen-Pfade (Source:Destination)
    datas = [
        (f"resources{os.sep}*", "resources"),
        (f"themes{os.sep}*.json", "themes"),
    ]
    
    # Argumente für PyInstaller
    args = [
        'main.py',                    # Entry point
        '--name=amdtr',               # App-Name
        '--icon=amdtr-ico.png',       # Icon-File
        '--onefile',                  # Einzelne EXE
        '--windowed',                 # Keine Console
        '--clean',                    # Cache leeren
    ]
    
    # Daten-Pfade hinzufügen
    for src, dst in datas:
        args.append(f'--add-data={src}{separator}{dst}')
    
    print(f"[*] Starting build for {platform.system()}...")
    
    PyInstaller.__main__.run(args)
    
    print("\n[+] Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
