"""
Wikilink-Resolver für [[note-name]] Navigation.

Implementiert:
- Case-insensitive Wikilink-Auflösung
- YAML Front-matter Aliases-Unterstützung  
- Wikilink-Extraktion aus Markdown-Text
- Backlinks-Tracking für bidirektionale Navigation
"""

from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set

from core.workspace import Workspace


# Regex für [[wikilink]] Syntax
WIKILINK_PATTERN = re.compile(r'\[\[([^\[\]]+)\]\]')


@dataclass
class WikilinkInfo:
    """Information über einen Wikilink."""
    link_text: str              # Der Text zwischen [[ ]]
    start_pos: int              # Start-Position im Text
    end_pos: int                # End-Position im Text
    resolved_path: Path | None  # Aufgelöster Dateipfad (None wenn nicht gefunden)


@dataclass
class DocumentLinks:
    """Alle Links eines Dokuments."""
    source_path: Path
    outgoing_links: List[WikilinkInfo] = field(default_factory=list)
    
    @property
    def valid_links(self) -> List[WikilinkInfo]:
        """Nur die Links die zu existierenden Dateien zeigen."""
        return [link for link in self.outgoing_links if link.resolved_path]
    
    @property 
    def broken_links(self) -> List[WikilinkInfo]:
        """Links zu nicht-existierenden Dateien."""
        return [link for link in self.outgoing_links if not link.resolved_path]


class WikilinkResolver:
    """
    Löst Wikilinks zu Dateipfaden auf und verwaltet Backlinks.
    """
    
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self._link_cache: Dict[Path, DocumentLinks] = {}
        self._backlinks_cache: Dict[Path, Set[Path]] = {}
        self._aliases_cache: Dict[str, Path] = {}  # alias -> file_path
        
    # ── Wikilink-Auflösung ────────────────────────────────────────────
    
    def resolve_wikilink(self, link_text: str) -> Path | None:
        """
        Löst einen Wikilink-Text zu einem Dateipfad auf.
        
        Suchstrategie:
        1. Exakte Übereinstimmung mit Datei-Stem (case-insensitive)
        2. Alias-Matching aus YAML Front-matter (falls implementiert)
        3. Teilstring-Matching für mehrdeutige Links
        """
        link_text = link_text.strip()
        if not link_text:
            return None
            
        link_lower = link_text.lower()
        
        # 1. Direkte Stem-Auflösung über Workspace
        resolved = self.workspace.resolve_wikilink(link_text)
        if resolved:
            return resolved
        
        # 2. Alias-Auflösung (TODO: Integration mit Front-matter Parser)
        if link_lower in self._aliases_cache:
            return self._aliases_cache[link_lower]
            
        # 3. Fallback: Fuzzy-Matching über alle Notizen
        return self._fuzzy_resolve(link_text)
    
    def _fuzzy_resolve(self, link_text: str) -> Path | None:
        """
        Fuzzy-Matching für mehrdeutige Wikilinks.
        Sucht nach Teilstring-Matches im Dateinamen.
        """
        link_lower = link_text.lower()
        candidates = []
        
        for note_path in self.workspace.all_notes():
            stem_lower = note_path.stem.lower()
            if link_lower in stem_lower:
                candidates.append((stem_lower.find(link_lower), note_path))
        
        if candidates:
            # Sortiere nach Position des Matches (frühere Matches bevorzugt)
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        
        return None
    
    # ── Link-Extraktion ───────────────────────────────────────────────
    
    def extract_wikilinks(self, text: str, source_path: Path) -> DocumentLinks:
        """
        Extrahiert alle Wikilinks aus einem Markdown-Text.
        
        Returns:
            DocumentLinks mit allen gefundenen Links und deren Auflösungen
        """
        doc_links = DocumentLinks(source_path=source_path)
        
        for match in WIKILINK_PATTERN.finditer(text):
            link_text = match.group(1).strip()
            start_pos = match.start()
            end_pos = match.end()
            
            resolved_path = self.resolve_wikilink(link_text)
            
            wikilink = WikilinkInfo(
                link_text=link_text,
                start_pos=start_pos,
                end_pos=end_pos,
                resolved_path=resolved_path
            )
            doc_links.outgoing_links.append(wikilink)
        
        # Cache aktualisieren
        self._link_cache[source_path] = doc_links
        self._update_backlinks_cache(source_path, doc_links)
        
        return doc_links
    
    def _update_backlinks_cache(self, source_path: Path, doc_links: DocumentLinks) -> None:
        """Aktualisiert den Backlinks-Cache basierend auf den ausgehenden Links."""
        # Alte Backlinks für diese Datei entfernen
        for target_paths in self._backlinks_cache.values():
            target_paths.discard(source_path)
        
        # Neue Backlinks hinzufügen
        for link in doc_links.valid_links:
            target_path = link.resolved_path
            if target_path not in self._backlinks_cache:
                self._backlinks_cache[target_path] = set()
            self._backlinks_cache[target_path].add(source_path)
    
    # ── Cache-Management ──────────────────────────────────────────────
    
    def get_cached_links(self, source_path: Path) -> DocumentLinks | None:
        """Gibt gecachte Links für eine Datei zurück."""
        return self._link_cache.get(source_path)
    
    def get_backlinks(self, target_path: Path) -> Set[Path]:
        """Gibt alle Dateien zurück die auf target_path verlinken."""
        return self._backlinks_cache.get(target_path, set()).copy()
    
    def invalidate_cache(self, file_path: Path | None = None) -> None:
        """
        Invalidiert Cache-Einträge.
        
        Args:
            file_path: Spezifische Datei oder None für kompletten Cache
        """
        if file_path:
            self._link_cache.pop(file_path, None)
            # Backlinks für diese Datei aus dem Cache entfernen
            for target_paths in self._backlinks_cache.values():
                target_paths.discard(file_path)
        else:
            self._link_cache.clear()
            self._backlinks_cache.clear()
    
    # ── Workspace-Integration ─────────────────────────────────────────
    
    def update_aliases_from_frontmatter(self, file_path: Path, aliases: List[str]) -> None:
        """
        Aktualisiert Alias-Cache basierend auf YAML Front-matter.
        TODO: Integration mit Front-matter Parser
        """
        # Alte Aliases für diese Datei entfernen
        old_aliases = [alias for alias, path in self._aliases_cache.items() if path == file_path]
        for alias in old_aliases:
            del self._aliases_cache[alias]
        
        # Neue Aliases hinzufügen
        for alias in aliases:
            alias_lower = alias.lower().strip()
            if alias_lower:
                self._aliases_cache[alias_lower] = file_path
    
    def get_all_linkable_notes(self) -> List[tuple[str, Path]]:
        """
        Gibt alle linkbaren Notizen zurück für Auto-Completion.
        
        Returns:
            Liste von (display_name, file_path) Tupeln
        """
        notes = []
        
        # Alle Dateien nach Stem
        for note_path in self.workspace.all_notes():
            notes.append((note_path.stem, note_path))
        
        # Alle Aliases hinzufügen
        for alias, file_path in self._aliases_cache.items():
            notes.append((alias, file_path))
        
        return sorted(notes, key=lambda x: x[0].lower())
    
    # ── Debugging & Statistiken ────────────────────────────────────────
    
    def get_link_statistics(self) -> Dict[str, int]:
        """Gibt Statistiken über Links im Workspace zurück."""
        total_outgoing = sum(len(doc.outgoing_links) for doc in self._link_cache.values())
        total_valid = sum(len(doc.valid_links) for doc in self._link_cache.values())
        total_broken = sum(len(doc.broken_links) for doc in self._link_cache.values())
        total_files_with_links = len(self._link_cache)
        total_files_with_backlinks = len(self._backlinks_cache)
        
        return {
            'total_outgoing_links': total_outgoing,
            'valid_links': total_valid,
            'broken_links': total_broken,
            'files_with_outgoing_links': total_files_with_links,
            'files_with_backlinks': total_files_with_backlinks,
            'total_aliases': len(self._aliases_cache),
        }