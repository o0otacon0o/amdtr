"""
SearchIndex — SQLite FTS5-based full-text search for the workspace.
"""

from __future__ import annotations
import sqlite3
import os
from pathlib import Path
from typing import List, Tuple


class SearchIndex:
    """
    Manages an SQLite FTS5 search index for Markdown files.
    Stores paths, titles, and the full text.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._setup_table()

    def _setup_table(self) -> None:
        """Creates the FTS5 table if it does not exist."""
        cursor = self._conn.cursor()
        # fts5 table for lightning-fast search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                path UNINDEXED, 
                title, 
                content,
                mtime UNINDEXED,
                tokenize='unicode61'
            )
        """)
        self._conn.commit()

    def get_indexed_mtime(self, path: Path) -> float:
        """Returns the last known modified time of a file from the index."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT mtime FROM notes_fts WHERE path = ?", (str(path),))
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def add_or_update(self, path: Path, content: str) -> None:
        """Adds a file to the index or updates it."""
        self.batch_add([(path, content)])

    def batch_add(self, entries: List[Tuple[Path, str]]) -> None:
        """Adds multiple files in a single transaction."""
        if not entries:
            return
            
        cursor = self._conn.cursor()
        try:
            for path, content in entries:
                rel_path = str(path)
                title = path.stem
                mtime = path.stat().st_mtime if path.exists() else 0
                
                # Delete old entry
                cursor.execute("DELETE FROM notes_fts WHERE path = ?", (rel_path,))
                # Insert new
                cursor.execute(
                    "INSERT INTO notes_fts(path, title, content, mtime) VALUES (?, ?, ?, ?)",
                    (rel_path, title, content, mtime)
                )
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            print(f"[!] Batch indexing error: {e}")

    def remove(self, path: Path) -> None:
        """Removes a file from the index."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM notes_fts WHERE path = ?", (str(path),))
        self._conn.commit()

    def search(self, query: str) -> List[Tuple[str, str, str]]:
        """
        Executes a full-text search.
        Supports automatic prefix search (wildcards).
        """
        if not query:
            return []

        # Prepare query for FTS5: append * to words for prefix search
        # "my house" becomes "my* house*"
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
        """Clears the entire index."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM notes_fts")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
