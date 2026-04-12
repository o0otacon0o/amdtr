"""
Workspace — repräsentiert ein geöffnetes Verzeichnis.

Kein Qt hier: reines Python-Datenmodell. Qt-Code gehört in ui/.
Diese Trennung (Model von View trennen) macht Unit-Tests einfach
und hält den Code wartbar wenn die UI sich ändert.
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from .search_index import SearchIndex


# Dateierweiterungen die die App als Notizen behandelt.
NOTE_EXTENSIONS = frozenset({".md", ".mmd", ".txt"})


@dataclass
class Workspace:
    """Ein Workspace ist ein Verzeichnis auf der Festplatte."""

    root: Path
    _index: Optional[SearchIndex] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"Not a directory: {self.root}")
        
        # Meta-Verzeichnis sicherstellen
        self.ensure_meta_dir()
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
        """Gibt eine Liste aller Markdown-Dateien im Workspace zurück (ohne Meta-Ordner)."""
        notes = []
        for ext in NOTE_EXTENSIONS:
            notes.extend(self.root.rglob(f"*{ext}"))
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
        .amdtr/ im Workspace-Root enthält:
          config.toml  — workspace-spezifische Einstellungen
          index.db     — SQLite FTS5-Suchindex
        """
        return self.root / ".amdtr"

    def ensure_meta_dir(self) -> Path:
        self.meta_dir.mkdir(exist_ok=True)
        return self.meta_dir

    # ── Display helpers ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.root.name

    def __repr__(self) -> str:
        return f"Workspace({self.root})"
