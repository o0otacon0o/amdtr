"""
SearchIndex — SQLite FTS5-basierte Volltextsuche für den Workspace.
"""

from __future__ import annotations
import sqlite3
import os
from pathlib import Path
from typing import List, Tuple


class SearchIndex:
    """
    Verwaltet einen SQLite FTS5 Suchindex für Markdown-Dateien.
    Speichert Pfade, Titel und den Volltext.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._setup_table()

    def _setup_table(self) -> None:
        """Erstellt die FTS5-Tabelle falls nicht vorhanden."""
        cursor = self._conn.cursor()
        # fts5 Tabelle für blitzschnelle Suche
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                path UNINDEXED, 
                title, 
                content,
                tokenize='unicode61'
            )
        """)
        self._conn.commit()

    def add_or_update(self, path: Path, content: str) -> None:
        """Fügt eine Datei zum Index hinzu oder aktualisiert sie."""
        rel_path = str(path)
        title = path.stem
        
        cursor = self._conn.cursor()
        # Erst alten Eintrag löschen (falls vorhanden)
        cursor.execute("DELETE FROM notes_fts WHERE path = ?", (rel_path,))
        # Neu einfügen
        cursor.execute(
            "INSERT INTO notes_fts(path, title, content) VALUES (?, ?, ?)",
            (rel_path, title, content)
        )
        self._conn.commit()

    def remove(self, path: Path) -> None:
        """Entfernt eine Datei aus dem Index."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM notes_fts WHERE path = ?", (str(path),))
        self._conn.commit()

    def search(self, query: str) -> List[Tuple[str, str, str]]:
        """
        Führt eine Volltextsuche aus.
        Unterstützt automatische Präfix-Suche (Wildcards).
        """
        if not query:
            return []

        # Query für FTS5 aufbereiten: Wörter mit * für Präfix-Suche versehen
        # Aus "mein haus" wird "mein* haus*"
        words = query.split()
        if not words:
            return []
        
        fts_query = " AND ".join(f"{w}*" for w in words)

        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    path, 
                    title, 
                    snippet(notes_fts, 2, '==', '==', '...', 20) as excerpt
                FROM notes_fts 
                WHERE notes_fts MATCH ? 
                ORDER BY rank
                LIMIT 50
            """, (fts_query,))
            return cursor.fetchall()
        except sqlite3.OperationalError:
            return []

    def clear(self) -> None:
        """Löscht den gesamten Index."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM notes_fts")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
