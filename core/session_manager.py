"""
SessionManager — Verwaltung der Sitzungs-Persistierung.

Kapselt:
- Offene Tabs und deren Zustand
- Cursor- und Scroll-Positionen  
- Crash-Recovery
- Workspace-Session
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Any
import json
from PyQt6.QtCore import QObject, QTimer


@dataclass
class TabSession:
    """Zustand eines einzelnen Tabs."""
    file_path: str
    cursor_line: int = 0
    cursor_column: int = 0
    scroll_position: int = 0
    is_active: bool = False


@dataclass
class WorkspaceSession:
    """Zustand einer Workspace-Sitzung."""
    workspace_root: str
    open_tabs: list[TabSession]
    active_tab_index: int = -1
    sidebar_width: int = 260
    preview_visible: bool = True
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.open_tabs = []


class SessionManager(QObject):
    """
    Verwaltet Session-Persistierung für Crash-Recovery.
    
    Speichert automatisch:
    - Offene Dateien und deren Editor-Zustand
    - Window-Geometrie und Panel-Größen
    - Aktiver Tab und Cursor-Positionen
    """
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_session: Optional[WorkspaceSession] = None
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save_session)
        self._auto_save_timer.start(5000)  # alle 5 Sekunden speichern
        
    def start_workspace_session(self, workspace_root: Path) -> None:
        """Startet eine neue Workspace-Session."""
        self._current_session = WorkspaceSession(str(workspace_root))
        self._load_session()
        
    def end_session(self) -> None:
        """Beendet die aktuelle Session und speichert sie."""
        if self._current_session:
            self._save_session()
            self._current_session = None
            
    def add_tab(self, file_path: Path, is_active: bool = False) -> None:
        """Fügt einen Tab zur Session hinzu."""
        if not self._current_session:
            return
            
        # Vorhandenen Tab-Eintrag entfernen
        self._remove_tab(file_path)
        
        # Neuen Tab hinzufügen
        tab = TabSession(
            file_path=str(file_path),
            is_active=is_active
        )
        self._current_session.open_tabs.append(tab)
        
        if is_active:
            self._current_session.active_tab_index = len(self._current_session.open_tabs) - 1
            
    def remove_tab(self, file_path: Path) -> None:
        """Entfernt einen Tab aus der Session."""
        self._remove_tab(file_path)
        
    def update_tab_state(self, file_path: Path, cursor_line: int, cursor_column: int, scroll_position: int) -> None:
        """Aktualisiert Editor-Zustand eines Tabs."""
        if not self._current_session:
            return
            
        for tab in self._current_session.open_tabs:
            if tab.file_path == str(file_path):
                tab.cursor_line = cursor_line
                tab.cursor_column = cursor_column
                tab.scroll_position = scroll_position
                break
                
    def set_active_tab(self, file_path: Path) -> None:
        """Setzt den aktiven Tab."""
        if not self._current_session:
            return
            
        for i, tab in enumerate(self._current_session.open_tabs):
            tab.is_active = (tab.file_path == str(file_path))
            if tab.is_active:
                self._current_session.active_tab_index = i
                
    def get_session_data(self) -> Optional[dict[str, Any]]:
        """Gibt die aktuelle Session als Dictionary zurück."""
        if not self._current_session:
            return None
            
        return {
            'workspace_root': self._current_session.workspace_root,
            'open_tabs': [asdict(tab) for tab in self._current_session.open_tabs],
            'active_tab_index': self._current_session.active_tab_index,
            'sidebar_width': self._current_session.sidebar_width,
            'preview_visible': self._current_session.preview_visible
        }
        
    def restore_from_data(self, data: dict[str, Any]) -> WorkspaceSession:
        """Erstellt Session aus Dictionary-Daten."""
        workspace_root = data.get('workspace_root', '')
        session = WorkspaceSession(workspace_root)
        
        session.active_tab_index = data.get('active_tab_index', -1)
        session.sidebar_width = data.get('sidebar_width', 260)
        session.preview_visible = data.get('preview_visible', True)
        
        # Tabs wiederherstellen
        for tab_data in data.get('open_tabs', []):
            tab = TabSession(
                file_path=tab_data['file_path'],
                cursor_line=tab_data.get('cursor_line', 0),
                cursor_column=tab_data.get('cursor_column', 0),
                scroll_position=tab_data.get('scroll_position', 0),
                is_active=tab_data.get('is_active', False)
            )
            session.open_tabs.append(tab)
            
        return session
    
    def _get_session_file_path(self) -> Optional[Path]:
        """Pfad zur Session-Datei im Workspace."""
        if not self._current_session:
            return None
            
        workspace_root = Path(self._current_session.workspace_root)
        return workspace_root / '.amdtr' / 'session.json'
        
    def _save_session(self) -> None:
        """Speichert Session in .amdtr/session.json"""
        session_file = self._get_session_file_path()
        if not session_file:
            return
            
        try:
            session_file.parent.mkdir(parents=True, exist_ok=True)
            data = self.get_session_data()
            if data:
                session_file.write_text(
                    json.dumps(data, indent=2), 
                    encoding='utf-8'
                )
        except (OSError, json.JSONEncodeError):
            pass  # Session-Speichern sollte nie die App zum Absturz bringen
            
    def _load_session(self) -> None:
        """Lädt Session aus .amdtr/session.json"""
        session_file = self._get_session_file_path()
        if not session_file or not session_file.exists():
            return
            
        try:
            data = json.loads(session_file.read_text(encoding='utf-8'))
            restored_session = self.restore_from_data(data)
            self._current_session = restored_session
        except (OSError, json.JSONDecodeError):
            pass  # Session-Laden sollte nie die App zum Absturz bringen
            
    def _auto_save_session(self) -> None:
        """Auto-Save Timer Callback."""
        if self._current_session:
            self._save_session()
            
    def _remove_tab(self, file_path: Path) -> None:
        """Hilfsmethode: Entfernt Tab aus der Liste."""
        if not self._current_session:
            return
            
        file_path_str = str(file_path)
        self._current_session.open_tabs = [
            tab for tab in self._current_session.open_tabs 
            if tab.file_path != file_path_str
        ]
        
        # Active-Index anpassen wenn nötig
        if (self._current_session.active_tab_index >= 
            len(self._current_session.open_tabs)):
            self._current_session.active_tab_index = (
                len(self._current_session.open_tabs) - 1
            )