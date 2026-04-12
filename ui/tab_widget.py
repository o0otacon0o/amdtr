"""
TabWidget — verwaltet geöffnete Dateien als Tabs.

Qt-Konzept: QTabWidget
  Container der genau ein Kind-Widget gleichzeitig zeigt, mit
  einer Tab-Leiste zum Wechseln. Key-Properties:
    setTabsClosable(True)  → × Button pro Tab
    setMovable(True)       → Tabs per Drag umordnen
    setDocumentMode(True)  → Saubereres Look, kein Rahmen um Tab-Inhalt

  Wichtige Signals:
    tabCloseRequested(int index) → × wurde geklickt
    currentChanged(int index)   → aktiver Tab hat gewechselt
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
    """Wird angezeigt solange keine Datei geöffnet ist."""

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
    Verwaltet geöffnete Dateien. Pro Datei ein Tab.

    Verhindert doppeltes Öffnen: wenn eine Datei schon offen ist,
    wird nur zum bestehenden Tab gewechselt.
    """

    active_file_changed = pyqtSignal(object)  # Path | None
    dirty_state_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setElideMode(Qt.TextElideMode.ElideMiddle)

        # Mapping: aufgelöster Pfad → Tab-Index für schnelle Lookups
        self._open_paths: dict[Path, int] = {}
        
        # Wikilink-System
        self._workspace: Workspace | None = None
        self._wikilink_resolver: WikilinkResolver | None = None
        
        # Theme-System
        self._current_theme: Theme | None = None

        # Welcome-Screen als initialer Inhalt
        self._welcome = WelcomeWidget()
        idx = self.addTab(self._welcome, "Welcome")
        # Den × Button am Welcome-Tab entfernen
        self.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)

        self.tabCloseRequested.connect(self._on_close_requested)
        self.currentChanged.connect(self._on_current_changed)

    # ── Public API ────────────────────────────────────────────────────

    def set_theme(self, theme: Theme) -> None:
        """Propagiert das Theme an alle Tabs."""
        self._current_theme = theme
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, EditorPreviewSplit):
                widget.set_theme(theme)

    def open_file(self, path: Path) -> None:
        """Datei öffnen oder zu ihr wechseln falls schon offen."""
        path = path.resolve()

        # Schon offen → nur zu diesem Tab wechseln
        if path in self._open_paths:
            self.setCurrentIndex(self._open_paths[path])
            return

        editor = EditorPreviewSplit(path)

        # Wikilink-Resolver mit Editor verbinden
        if self._wikilink_resolver:
            editor.set_wikilink_resolver(self._wikilink_resolver)
            
        # Theme anwenden falls schon gesetzt
        if self._current_theme:
            editor.set_theme(self._current_theme)

        # Signals verbinden
        editor.dirty_state_changed.connect(
            lambda dirty, p=path: self._on_editor_dirty_changed(p, dirty)
        )
        
        # Wikilink-Navigation-Signal verbinden
        editor.wikilink_requested.connect(self.open_file)

        idx = self.addTab(editor, path.name)
        self.setTabToolTip(idx, str(path))

        # Welcome-Tab entfernen wenn erste echte Datei geöffnet wird
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
        Setzt den aktiven Workspace und initialisiert Wikilink-System.
        """
        self._workspace = workspace
        
        if workspace:
            # Wikilink-Resolver für neuen Workspace erstellen
            self._wikilink_resolver = WikilinkResolver(workspace)
            
            # Alle bereits geöffneten Editoren mit Resolver verbinden
            for i in range(self.count()):
                widget = self.widget(i)
                if isinstance(widget, EditorPreviewSplit):
                    widget.set_wikilink_resolver(self._wikilink_resolver)
        else:
            self._wikilink_resolver = None
            
            # Resolver von allen Editoren entfernen
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

        # Welcome-Screen zurückbringen wenn alle Tabs geschlossen
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
        # Tab-Label mit "●" markieren wenn ungespeichert
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
        Baut das Path→Index-Mapping neu auf.
        Muss nach jedem addTab/removeTab aufgerufen werden, weil
        QTabWidget Indizes nach Entfernen eines Tabs verschiebt.
        """
        self._open_paths = {}
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, EditorPreviewSplit):
                self._open_paths[w.path()] = i
