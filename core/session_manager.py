"""
SessionManager — Management of session persistence.

Encapsulates:
- Open tabs and their state
- Cursor and scroll positions  
- Crash recovery
- Workspace session
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Any
import json
from PyQt6.QtCore import QObject, QTimer


@dataclass
class TabSession:
    """State of a single tab."""
    file_path: str
    cursor_line: int = 0
    cursor_column: int = 0
    scroll_position: int = 0
    is_active: bool = False


@dataclass
class WorkspaceSession:
    """State of a workspace session."""
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
    Manages session persistence for crash recovery.
    
    Automatically saves:
    - Open files and their editor state
    - Window geometry and panel sizes
    - Active tab and cursor positions
    """
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_session: Optional[WorkspaceSession] = None
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save_session)
        self._auto_save_timer.start(5000)  # save every 5 seconds
        
    def start_workspace_session(self, workspace_root: Path) -> None:
        """Starts a new workspace session."""
        self._current_session = WorkspaceSession(str(workspace_root))
        self._load_session()
        
    def end_session(self) -> None:
        """Ends the current session and saves it."""
        if self._current_session:
            self._save_session()
            self._current_session = None
            
    def add_tab(self, file_path: Path, is_active: bool = False) -> None:
        """Adds a tab to the session."""
        if not self._current_session:
            return
            
        # Remove existing tab entry
        self._remove_tab(file_path)
        
        # Add new tab
        tab = TabSession(
            file_path=str(file_path),
            is_active=is_active
        )
        self._current_session.open_tabs.append(tab)
        
        if is_active:
            self._current_session.active_tab_index = len(self._current_session.open_tabs) - 1
            
    def remove_tab(self, file_path: Path) -> None:
        """Removes a tab from the session."""
        self._remove_tab(file_path)
        
    def update_tab_state(self, file_path: Path, cursor_line: int, cursor_column: int, scroll_position: int) -> None:
        """Updates the editor state of a tab."""
        if not self._current_session:
            return
            
        for tab in self._current_session.open_tabs:
            if tab.file_path == str(file_path):
                tab.cursor_line = cursor_line
                tab.cursor_column = cursor_column
                tab.scroll_position = scroll_position
                break
                
    def set_active_tab(self, file_path: Path) -> None:
        """Sets the active tab."""
        if not self._current_session:
            return
            
        for i, tab in enumerate(self._current_session.open_tabs):
            tab.is_active = (tab.file_path == str(file_path))
            if tab.is_active:
                self._current_session.active_tab_index = i
                
    def get_session_data(self) -> Optional[dict[str, Any]]:
        """Returns the current session as a dictionary."""
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
        """Creates a session from dictionary data."""
        workspace_root = data.get('workspace_root', '')
        session = WorkspaceSession(workspace_root)
        
        session.active_tab_index = data.get('active_tab_index', -1)
        session.sidebar_width = data.get('sidebar_width', 260)
        session.preview_visible = data.get('preview_visible', True)
        
        # Restore tabs
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
        """Path to the session file in the central workspace data directory."""
        if not self._current_session:
            return None
            
        from .workspace import Workspace
        workspace_root = Path(self._current_session.workspace_root)
        try:
            ws = Workspace(workspace_root)
            return ws.meta_dir / 'session.json'
        except ValueError:
            return None
        
    def _save_session(self) -> None:
        """Saves session in <CentralDataDir>/workspaces/<Hash>/session.json"""
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
            pass  # Saving session should never crash the app
            
    def _load_session(self) -> None:
        """Loads session from .amdtr/session.json"""
        session_file = self._get_session_file_path()
        if not session_file or not session_file.exists():
            return
            
        try:
            data = json.loads(session_file.read_text(encoding='utf-8'))
            restored_session = self.restore_from_data(data)
            self._current_session = restored_session
        except (OSError, json.JSONDecodeError):
            pass  # Loading session should never crash the app
            
    def _auto_save_session(self) -> None:
        """Auto-save timer callback."""
        if self._current_session:
            self._save_session()
            
    def _remove_tab(self, file_path: Path) -> None:
        """Helper method: removes a tab from the list."""
        if not self._current_session:
            return
            
        file_path_str = str(file_path)
        self._current_session.open_tabs = [
            tab for tab in self._current_session.open_tabs 
            if tab.file_path != file_path_str
        ]
        
        # Adjust active index if necessary
        if (self._current_session.active_tab_index >= 
            len(self._current_session.open_tabs)):
            self._current_session.active_tab_index = (
                len(self._current_session.open_tabs) - 1
            )
