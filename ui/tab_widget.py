"""
TabWidget — manages opened files as tabs.

Qt Concept: QTabWidget
  Container that shows exactly one child widget at a time, with
  a tab bar for switching. Key properties:
    setTabsClosable(True)  → × button per tab
    setMovable(True)       → reorder tabs via drag and drop
    setDocumentMode(True)  → cleaner look, no border around tab content

  Important signals:
    tabCloseRequested(int index) → × was clicked
    currentChanged(int index)   → active tab has changed
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QLabel,
    QTabBar, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.editor_preview_split import EditorPreviewSplit
from core.wikilink_resolver import WikilinkResolver
from core.workspace import Workspace
from themes.schema import Theme


# ── Welcoming screen ──────────────────────────────────────────────────

class WelcomeWidget(QWidget):
    """Displayed as long as no file is open."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        title = QLabel("amdtr")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: 200; color: #888;")

        shortcuts = QLabel(
            "Open workspace:  Ctrl+Shift+O\n"
            "Open file:           Ctrl+O\n"
            "Command palette:  Ctrl+P"
        )
        shortcuts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts.setStyleSheet(
            "font-family: monospace; font-size: 12px; color: #aaa; line-height: 1.8;"
        )

        layout.addWidget(title)
        layout.addSpacing(16)
        layout.addWidget(shortcuts)


# ── Tab widget ────────────────────────────────────────────────────────

class TabWidget(QTabWidget):
    """
    Manages open files. One tab per file.

    Prevents duplicate opening: if a file is already open,
    it just switches to the existing tab.
    """

    active_file_changed = pyqtSignal(object)  # Path | None
    dirty_state_changed = pyqtSignal()
    vim_status_changed = pyqtSignal(str)   # Mode + pending keys

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setElideMode(Qt.TextElideMode.ElideMiddle)

        # Mapping: resolved path → tab index for fast lookups
        self._open_paths: dict[Path, int] = {}
        
        # Wikilink system
        self._workspace: Workspace | None = None
        self._wikilink_resolver: WikilinkResolver | None = None
        
        # Theme system
        self._current_theme: Theme | None = None
        
        # Vim mode
        self._vim_mode = False

        # Welcome screen as initial content
        self._welcome = WelcomeWidget()
        idx = self.addTab(self._welcome, "Welcome")
        # Remove the × button on the welcome tab
        self.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)

        self.tabCloseRequested.connect(self._on_close_requested)
        self.currentChanged.connect(self._on_current_changed)

    # ── Public API ────────────────────────────────────────────────────

    def set_theme(self, theme: Theme) -> None:
        """Propagates the theme to all tabs."""
        self._current_theme = theme
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, EditorPreviewSplit):
                widget.set_theme(theme)

    def set_vim_mode(self, enabled: bool) -> None:
        """Enables or disables Vim mode in all open editors."""
        self._vim_mode = enabled
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, EditorPreviewSplit):
                widget.set_vim_mode(enabled)

    def open_file(self, path: Path) -> None:
        """Opens a file or switches to it if already open."""
        path = path.resolve()

        # Already open → just switch to this tab
        if path in self._open_paths:
            self.setCurrentIndex(self._open_paths[path])
            return

        editor = EditorPreviewSplit(path)

        # Apply current settings to new editor
        if self._vim_mode:
            editor.set_vim_mode(True)

        # Connect wikilink resolver with editor
        if self._wikilink_resolver:
            editor.set_wikilink_resolver(self._wikilink_resolver)
            
        # Apply theme if already set
        if self._current_theme:
            editor.set_theme(self._current_theme)

        # Connect signals
        editor.dirty_state_changed.connect(
            lambda dirty, p=path: self._on_editor_dirty_changed(p, dirty)
        )
        
        # Connect wikilink navigation signal
        editor.wikilink_requested.connect(self.open_file)
        
        # Connect vim status signal
        editor.vim_status_changed.connect(self.vim_status_changed.emit)

        idx = self.addTab(editor, path.name)
        self.setTabToolTip(idx, str(path))

        # Remove welcome tab when the first real file is opened
        welcome_idx = self.indexOf(self._welcome)
        if welcome_idx != -1:
            self.removeTab(welcome_idx)

        self._rebuild_path_index()
        self.setCurrentWidget(editor)

    def save_current(self) -> None:
        w = self.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            w.save()
            self._update_tab_label(w)

    def save_all(self) -> None:
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, EditorPreviewSplit):
                w.save()
                self._update_tab_label(w)

    def has_unsaved_changes(self) -> bool:
        return any(
            isinstance(self.widget(i), EditorPreviewSplit)
            and self.widget(i).is_dirty()
            for i in range(self.count())
        )
    
    def set_workspace(self, workspace: Workspace | None) -> None:
        """
        Sets the active workspace and initializes the wikilink system.
        """
        self._workspace = workspace
        
        if workspace:
            # Create wikilink resolver for new workspace
            self._wikilink_resolver = WikilinkResolver(workspace)
            
            # Connect all already open editors with the resolver
            for i in range(self.count()):
                widget = self.widget(i)
                if isinstance(widget, EditorPreviewSplit):
                    widget.set_wikilink_resolver(self._wikilink_resolver)
        else:
            self._wikilink_resolver = None
            
            # Remove resolver from all editors
            for i in range(self.count()):
                widget = self.widget(i)
                if isinstance(widget, EditorPreviewSplit):
                    widget.set_wikilink_resolver(None)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_close_requested(self, index: int) -> None:
        w = self.widget(index)

        if isinstance(w, EditorPreviewSplit) and w.is_dirty():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{w.path().name}' has unsaved changes. Save?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                w.save()

        if isinstance(w, EditorPreviewSplit):
            self._open_paths.pop(w.path(), None)

        self.removeTab(index)
        self._rebuild_path_index()

        # Bring back welcome screen if all tabs are closed
        if self.count() == 0:
            idx = self.addTab(self._welcome, "Welcome")
            self.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)

        self.dirty_state_changed.emit()

    def _on_current_changed(self, index: int) -> None:
        w = self.widget(index)
        if isinstance(w, EditorPreviewSplit):
            self.active_file_changed.emit(w.path())
        else:
            self.active_file_changed.emit(None)

    def _on_editor_dirty_changed(self, path: Path, dirty: bool) -> None:
        # Mark tab label with "●" if unsaved
        if path in self._open_paths:
            idx = self._open_paths[path]
            w = self.widget(idx)
            if isinstance(w, EditorPreviewSplit):
                self._update_tab_label(w)
        self.dirty_state_changed.emit()

    # ── Helpers ───────────────────────────────────────────────────────

    def _update_tab_label(self, editor: EditorPreviewSplit) -> None:
        idx = self.indexOf(editor)
        if idx == -1:
            return
        name = editor.path().name
        self.setTabText(idx, ("● " + name) if editor.is_dirty() else name)

    def _rebuild_path_index(self) -> None:
        """
        Rebuilds the Path→Index mapping.
        Must be called after every addTab/removeTab because QTabWidget
        shifts indices after removing a tab.
        """
        self._open_paths = {}
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, EditorPreviewSplit):
                self._open_paths[w.path()] = i
