import urllib.request
import os
from pathlib import Path

# Konfiguration
VENDOR_DIR = Path("resources/vendor")
DEPENDENCIES = {
    # JavaScript
    "marked.min.js": "https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js",
    "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11.0.0/dist/mermaid.min.js",
    "katex.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.js",
    "auto-render.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/contrib/auto-render.min.js",
    "highlight.min.js": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js",
    
    # CSS
    "katex.min.css": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.css",
    "github.min.css": "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css",
    "github-dark.min.css": "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github-dark.min.css"
}

def setup():
    print(f"--- amdtr Vendor Setup ---")
    
    # Verzeichnis erstellen
    if not VENDOR_DIR.exists():
        print(f"Erstelle Verzeichnis: {VENDOR_DIR}")
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    # Dateien herunterladen
    for filename, url in DEPENDENCIES.items():
        target_path = VENDOR_DIR / filename
        print(f"Lade herunter: {filename}...", end=" ", flush=True)
        try:
            # User-Agent hinzufügen, um Blockaden zu vermeiden
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(target_path, 'wb') as f:
                    f.write(response.read())
            print("ERFOLG")
        except Exception as e:
            print(f"FEHLER: {e}")

    print(f"\nSetup abgeschlossen. Alle Dateien befinden sich in {VENDOR_DIR}")

if __name__ == "__main__":
    setup()
