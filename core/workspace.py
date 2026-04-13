"""
Workspace — repräsentiert ein geöffnetes Verzeichnis.

Kein Qt hier: reines Python-Datenmodell. Qt-Code gehört in ui/.
Diese Trennung (Model von View trennen) macht Unit-Tests einfach
und hält den Code wartbar wenn die UI sich ändert.
"""

import hashlib
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from .search_index import SearchIndex


# Dateierweiterungen die die App als Notizen behandelt.
NOTE_EXTENSIONS = frozenset({".md", ".mmd", ".txt"})


def get_central_data_dir() -> Path:
    """Returns the central directory for application data."""
    if os.name == 'nt': # Windows
        base = Path(os.environ.get('APPDATA', Path.home())) / "amdtr"
    elif os.name == 'posix': # macOS/Linux
        # Follow XDG on Linux, standard Library on macOS
        import platform
        if platform.system() == 'Darwin':
            base = Path.home() / "Library" / "Application Support" / "amdtr"
        else:
            base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / ".local" / "share")) / "amdtr"
    else:
        base = Path.home() / ".amdtr"
    
    return base


@dataclass
class Workspace:
    """Ein Workspace ist ein Verzeichnis auf der Festplatte."""

    root: Path
    _index: Optional[SearchIndex] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"Not a directory: {self.root}")
        
        # Central Meta-Verzeichnis sicherstellen
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        # Index initialisieren
        self._index = SearchIndex(self.meta_dir / "index.db")

    @property
    def index(self) -> SearchIndex:
        """Gibt den Suchindex des Workspace zurück."""
        if self._index is None:
            self._index = SearchIndex(self.meta_dir / "index.db")
        return self._index

    # ── File discovery ────────────────────────────────────────────────

    def all_notes(self) -> list[Path]:
        """Gibt eine Liste aller Markdown-Dateien im Workspace zurück."""
        notes = []
        for ext in NOTE_EXTENSIONS:
            notes.extend(self.root.rglob(f"*{ext}"))
        
        # We no longer need to filter .amdtr from parts since it's central,
        # but we keep it for backward compatibility or in case users have 
        # local .amdtr folders from other versions.
        return sorted([n for n in notes if ".amdtr" not in n.parts])

    def resolve_wikilink(self, name: str) -> Path | None:
        """
        Findet eine Datei anhand ihres Stems (Dateiname ohne Extension).
        Wikilinks [[name]] matchen case-insensitiv.
        """
        name_lower = name.lower().strip()
        for note in self.all_notes():
            if note.stem.lower() == name_lower:
                return note
        return None

    def relative(self, path: Path) -> Path:
        """Gibt den Pfad relativ zum Workspace-Root zurück."""
        return path.relative_to(self.root)

    def is_note(self, path: Path) -> bool:
        return path.suffix.lower() in NOTE_EXTENSIONS

    # ── Metadata directory ────────────────────────────────────────────

    @property
    def meta_dir(self) -> Path:
        """
        Zentrales Verzeichnis für Workspace-Metadaten.
        Pfad: <CentralDataDir>/workspaces/<PathHash>/
        """
        # Unique Hash für den absoluten Pfad des Workspace erzeugen
        path_hash = hashlib.sha256(str(self.root).encode('utf-8')).hexdigest()[:16]
        return get_central_data_dir() / "workspaces" / path_hash

    # ── Display helpers ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.root.name

    def __repr__(self) -> str:
        return f"Workspace({self.root})"


    # ── Display helpers ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.root.name

    def __repr__(self) -> str:
        return f"Workspace({self.root})"
