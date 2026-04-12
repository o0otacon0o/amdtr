"""
DocumentModel — repräsentiert ein geöffnetes Markdown-Dokument.

Kapselt:
- Datei-Pfad und Text-Inhalt
- Dirty-State (ungespeicherte Änderungen)
- Undo/Redo-Stack
- Metadaten (Front-matter, Tags, Wikilinks)
- Cursor-Position und Scroll-State
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack

from core.wikilink_resolver import WikilinkResolver, WIKILINK_PATTERN


@dataclass
class DocumentMetadata:
    """YAML Front-matter und extrahierte Metadaten."""
    title: str = ""
    tags: list[str] = field(default_factory=list) 
    date: str = ""
    aliases: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)  # ausgehende Links
    
    @classmethod
    def from_frontmatter(cls, frontmatter: dict[str, Any]) -> DocumentMetadata:
        """Erstellt Metadaten aus geparsten YAML Front-matter."""
        return cls(
            title=frontmatter.get("title", ""),
            tags=frontmatter.get("tags", []) if isinstance(frontmatter.get("tags"), list) else [],
            date=frontmatter.get("date", ""),
            aliases=frontmatter.get("aliases", []) if isinstance(frontmatter.get("aliases"), list) else []
        )


class DocumentModel(QObject):
    """
    Model für ein einzelnes Markdown-Dokument.
    
    Signals:
        text_changed(str): Text wurde geändert
        dirty_state_changed(bool): Dirty-Status geändert  
        metadata_changed(): Metadaten wurden geupdatet
    """
    
    text_changed = pyqtSignal(str)
    dirty_state_changed = pyqtSignal(bool)
    metadata_changed = pyqtSignal()
    
    def __init__(self, file_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = file_path.resolve()
        self._text = ""
        self._dirty = False
        self._metadata = DocumentMetadata()
        
        # Wikilink-Resolver (wird von außen gesetzt)
        self._wikilink_resolver: WikilinkResolver | None = None
        
        # Undo/Redo wird später über QScintilla verwaltet
        # Hier nur als Placeholder für konsistente API
        self._undo_stack = QUndoStack(self)
        
        # Editor-State (wird von EditorPanel gesetzt)
        self._cursor_line = 0
        self._cursor_column = 0
        self._scroll_position = 0
        
    # ── Properties ────────────────────────────────────────────────────
    
    @property
    def path(self) -> Path:
        return self._path
        
    @property 
    def text(self) -> str:
        return self._text
        
    @text.setter
    def text(self, value: str) -> None:
        if self._text != value:
            self._text = value
            self._extract_metadata()
            self._set_dirty(True)
            self.text_changed.emit(value)
            
    @property
    def dirty(self) -> bool:
        return self._dirty
        
    @property
    def metadata(self) -> DocumentMetadata:
        return self._metadata
        
    @property
    def display_name(self) -> str:
        """Name für Tab-Anzeige: title aus Front-matter oder Dateiname."""
        if self._metadata.title:
            return self._metadata.title
        return self._path.stem
        
    # ── Editor State ──────────────────────────────────────────────────
    
    def set_cursor_position(self, line: int, column: int) -> None:
        """Cursor-Position für Session-Recovery speichern."""
        self._cursor_line = line
        self._cursor_column = column
        
    def get_cursor_position(self) -> tuple[int, int]:
        return self._cursor_line, self._cursor_column
        
    def set_scroll_position(self, position: int) -> None:
        """Scroll-Position für Session-Recovery speichern."""
        self._scroll_position = position
        
    def get_scroll_position(self) -> int:
        return self._scroll_position
    
    # ── Wikilink Integration ──────────────────────────────────────────
    
    def set_wikilink_resolver(self, resolver: WikilinkResolver | None) -> None:
        """Setzt den Wikilink-Resolver für Link-Auflösung."""
        self._wikilink_resolver = resolver
        # Re-extrahiere Metadaten mit neuem Resolver
        if resolver and self._text:
            self._extract_metadata()
    
    def resolve_wikilink_at_position(self, position: int) -> Path | None:
        """
        Löst einen Wikilink an der gegebenen Text-Position auf.
        Gibt None zurück wenn an der Position kein Wikilink ist.
        """
        if not self._wikilink_resolver:
            return None
            
        # Finde Wikilink an Position
        for match in WIKILINK_PATTERN.finditer(self._text):
            if match.start() <= position <= match.end():
                link_text = match.group(1).strip()
                return self._wikilink_resolver.resolve_wikilink(link_text)
        return None
    
    def get_wikilinks_info(self) -> list[tuple[str, int, int, bool]]:
        """
        Gibt alle Wikilinks mit Position und Gültigkeit zurück.
        
        Returns:
            Liste von (link_text, start_pos, end_pos, is_valid) Tupeln
        """
        if not self._wikilink_resolver:
            return []
        
        links_info = []
        for match in WIKILINK_PATTERN.finditer(self._text):
            link_text = match.group(1).strip()
            start_pos = match.start()
            end_pos = match.end()
            resolved = self._wikilink_resolver.resolve_wikilink(link_text)
            is_valid = resolved is not None
            links_info.append((link_text, start_pos, end_pos, is_valid))
        
        return links_info
    
    # ── File Operations ───────────────────────────────────────────────
    
    def load_from_disk(self) -> bool:
        """
        Lädt den Inhalt von der Festplatte.
        Gibt True zurück wenn erfolgreich.
        """
        try:
            text = self._path.read_text(encoding="utf-8")
            self._text = text
            self._extract_metadata()
            self._set_dirty(False)
            self.text_changed.emit(text)
            return True
        except (FileNotFoundError, UnicodeDecodeError, OSError):
            # Neue Datei oder Encoding-Problem
            self._text = ""
            self._metadata = DocumentMetadata()
            self._set_dirty(False)
            self.text_changed.emit("")
            return False
            
    def save_to_disk(self) -> bool:
        """
        Speichert den aktuellen Inhalt auf die Festplatte.
        Gibt True zurück wenn erfolgreich.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._text, encoding="utf-8")
            self._set_dirty(False)
            return True
        except OSError:
            return False
    
    # ── Private Methods ───────────────────────────────────────────────
    
    def _set_dirty(self, dirty: bool) -> None:
        """Dirty-Status ändern und Signal emittieren."""
        if self._dirty != dirty:
            self._dirty = dirty
            self.dirty_state_changed.emit(dirty)
            
    def _extract_metadata(self) -> None:
        """
        Extrahiert Metadaten aus dem aktuellen Text.
        Parst Front-matter und sammelt Wikilinks.
        """
        # Wikilinks extrahieren
        wikilinks = []
        for match in WIKILINK_PATTERN.finditer(self._text):
            link_text = match.group(1).strip()
            if link_text not in wikilinks:  # Duplikate vermeiden
                wikilinks.append(link_text)
        
        self._metadata.wikilinks = wikilinks
        
        # Wikilink-Resolver über neue Links informieren
        if self._wikilink_resolver:
            self._wikilink_resolver.extract_wikilinks(self._text, self._path)
        
        # TODO: Implement Front-matter parsing
        
        self.metadata_changed.emit()