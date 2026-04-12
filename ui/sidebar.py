"""
Sidebar — Dateibaum + Suche/Filter.

Qt-Konzept: Model/View-Architektur
  Qt trennt Daten (Model) von ihrer Darstellung (View).
  QFileSystemModel = das Model (liest das Dateisystem)
  QTreeView         = die View (zeigt Baumstruktur)
  QSortFilterProxyModel = sitzt zwischen Model und View,
    filtert/sortiert ohne das Original-Model zu verändern.

  Vorteil: dieselben Daten können von mehreren Views angezeigt
  werden, und Sortierung/Filterung kostet kein Re-Laden.

Qt-Konzept: pyqtSignal
  Eigene Signals werden als Klassen-Attribut mit pyqtSignal()
  deklariert. Jede Instanz bekommt eine eigene Kopie.
  Emit: self.file_activated.emit(path)
  Connect: sidebar.file_activated.connect(callable)
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTreeView, QLabel, QToolButton, QFrame, QSizePolicy,
    QMenu, QInputDialog, QMessageBox, QTabWidget,
)
from PyQt6.QtCore import (
    Qt, QSortFilterProxyModel, QModelIndex, pyqtSignal,
)
from PyQt6.QtGui import QFileSystemModel

from ui.outline_panel import OutlinePanel


class _RecursiveFilterProxy(QSortFilterProxyModel):
    # ... (rest of proxy code) ...
    """
    Proxy-Model mit rekursivem Filter:
    Ein Ordner wird angezeigt, wenn mindestens ein Kind den Filter erfüllt.

    Ohne diese Überschreibung würden Ordner bei aktivem Filter ausgeblendet
    — der Baum würde kollabieren und man könnte keine Dateien mehr sehen.
    """

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # Kein aktiver Filter → alles anzeigen
        if not self.filterRegularExpression().pattern():
            return True

        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)

        # Für Verzeichnisse: anzeigen wenn irgendein Kind passt
        if model.isDir(index):
            for i in range(model.rowCount(index)):
                if self.filterAcceptsRow(i, index):
                    return True
            return False

        # Für Dateien: Standard-Filter (Dateiname-Match)
        return super().filterAcceptsRow(source_row, source_parent)


class Sidebar(QWidget):
    """
    Linkes Panel: Workspace-Header + Suchleiste + Dateibaum/Gliederung.

    Signals:
      file_activated(Path)          — User doppelklickt eine Datei
      open_workspace_requested(Path) — User klickt "…" und wählt Ordner
      outline_item_clicked(int)      — User klickt auf Header in Gliederung
    """

    file_activated = pyqtSignal(Path)
    file_deleted = pyqtSignal(Path)
    open_workspace_requested = pyqtSignal(Path)
    outline_item_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(160)
        self.setMaximumWidth(600)

        self._workspace: Workspace | None = None

        # Model: repräsentiert das Dateisystem
        self._fs_model = QFileSystemModel()
        self._fs_model.setReadOnly(False)

        # Proxy: sitzt vor dem Model, übernimmt Filter und Sortierung
        self._proxy = _RecursiveFilterProxy()
        self._proxy.setSourceModel(self._fs_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)

        self._build_ui()

    # ── UI-Aufbau ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._tabs.setStyleSheet("QTabBar::tab { min-width: 80px; }")

        # Tab 1: Explorer
        explorer_widget = QWidget()
        explorer_layout = QVBoxLayout(explorer_widget)
        explorer_layout.setContentsMargins(0, 0, 0, 0)
        explorer_layout.setSpacing(0)
        explorer_layout.addWidget(self._build_search())
        explorer_layout.addWidget(self._build_tree(), stretch=1)
        
        self._tabs.addTab(explorer_widget, "Files")

        # Tab 2: Outline
        self._outline = OutlinePanel()
        self._outline.header_clicked.connect(self.outline_item_clicked.emit)
        self._tabs.addTab(self._outline, "Outline")

        root.addWidget(self._tabs)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFixedHeight(36)

        h = QHBoxLayout(frame)
        h.setContentsMargins(8, 0, 4, 0)
        h.setSpacing(4)

        self._lbl_workspace = QLabel("No workspace")
        self._lbl_workspace.setStyleSheet("font-size: 11px; font-weight: 600;")
        self._lbl_workspace.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        # elided text: bei zu wenig Platz wird "..." angehängt
        self._lbl_workspace.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        btn_open = QToolButton()
        btn_open.setText("…")
        btn_open.setToolTip("Open workspace folder (Ctrl+Shift+O)")
        btn_open.setFixedSize(22, 22)
        btn_open.clicked.connect(self._on_open_btn_clicked)

        h.addWidget(self._lbl_workspace)
        h.addWidget(btn_open)
        return frame

    def _build_search(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(34)
        h = QHBoxLayout(container)
        h.setContentsMargins(6, 4, 6, 4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter files…")
        self._search_input.setClearButtonEnabled(True)

        # textChanged: Signal das bei jeder Zeicheneingabe feuert
        # und den aktuellen Text als String mitgibt
        self._search_input.textChanged.connect(self._on_filter_changed)

        h.addWidget(self._search_input)
        return container

    def _build_tree(self) -> QTreeView:
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)

        # Kontextmenü aktivieren
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_custom_context_menu)

        # Nur die Name-Spalte anzeigen (0), Rest verstecken
        self._tree.setHeaderHidden(True)
        for col in range(1, 4):
            self._tree.hideColumn(col)

        self._tree.setAnimated(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setWordWrap(False)

        # Verhindert dass der User Dateien im Tree umbenennen kann
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

        # activated feuert bei Doppelklick ODER Enter-Taste
        self._tree.activated.connect(self._on_item_activated)

        return self._tree

    # ── Public API ────────────────────────────────────────────────────

    def set_workspace(self, ws: Workspace | None) -> None:
        """Wird von MainWindow aufgerufen wenn ein Workspace geöffnet oder geschlossen wird."""
        self._workspace = ws
        
        if ws is None:
            self._lbl_workspace.setText("No Workspace")
            self._lbl_workspace.setToolTip("")
            # Important: setRootPath("") on QFileSystemModel shows all system drives.
            # We set a path that doesn't exist or just hide the tree to keep it clean.
            self._fs_model.setRootPath("/__non_existent_path__")
            self._tree.setRootIndex(QModelIndex())
            self._tree.hide()
            return

        self._lbl_workspace.setText(ws.name)
        self._lbl_workspace.setToolTip(str(ws.root))
        self._tree.show()

        # setRootPath startet das Monitoring des Verzeichnisses.
        self._fs_model.setRootPath(str(ws.root))
        
        # Nur Notiz-Dateien anzeigen.
        self._fs_model.setNameFilters(["*.md", "*.mmd", "*.txt"])
        self._fs_model.setNameFilterDisables(False)

        # WICHTIG: Den Root-Index für die View setzen.
        # Da wir einen Proxy nutzen, müssen wir den Index mappen.
        source_index = self._fs_model.index(str(ws.root))
        proxy_index = self._proxy.mapFromSource(source_index)
        self._tree.setRootIndex(proxy_index)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_item_activated(self, proxy_index: QModelIndex) -> None:
        # Proxy-Index → Source-Index → Dateipfad
        source_index = self._proxy.mapToSource(proxy_index)

        if self._fs_model.isDir(source_index):
            return  # Ordner nicht öffnen, nur Dateien

        path = Path(self._fs_model.filePath(source_index))
        self.file_activated.emit(path)

    def _on_filter_changed(self, text: str) -> None:
        # setFilterFixedString: sucht nach exaktem Substring (case-insensitiv
        # weil wir setFilterCaseSensitivity gesetzt haben)
        self._proxy.setFilterFixedString(text)

        if text:
            # Bei aktivem Filter: gesamten Baum aufklappen damit Treffer sichtbar
            self._tree.expandAll()
        else:
            # Filter gelöscht: Baum wieder zuklappen
            self._tree.collapseAll()

    def _on_open_btn_clicked(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            self, "Open Workspace", str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self.open_workspace_requested.emit(Path(path))

    def _on_custom_context_menu(self, pos) -> None:
        """Erstellt und zeigt das Kontextmenü für Dateien/Ordner."""
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return

        source_index = self._proxy.mapToSource(index)
        file_path = Path(self._fs_model.filePath(source_index))
        is_dir = self._fs_model.isDir(source_index)

        menu = QMenu(self)
        
        # Aktionen definieren
        rename_act = menu.addAction("Rename")
        delete_act = menu.addAction("Delete")
        
        # Menü anzeigen und gewählte Aktion abfangen
        action = menu.exec(self._tree.mapToGlobal(pos))
        
        if action == rename_act:
            self._rename_file(source_index, file_path)
        elif action == delete_act:
            self._delete_file(file_path, is_dir)

    def _rename_file(self, source_index: QModelIndex, old_path: Path) -> None:
        """Benennt eine Datei oder einen Ordner um und aktualisiert den Index."""
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", QLineEdit.EchoMode.Normal, old_path.name
        )
        
        if ok and new_name and new_name != old_path.name:
            new_path = old_path.parent / new_name
            try:
                import os
                os.rename(old_path, new_path)
                
                # Index aktualisieren
                if self._workspace:
                    self._workspace.index.remove(old_path)
                    if not self._fs_model.isDir(source_index):
                        try:
                            content = new_path.read_text(encoding="utf-8")
                            self._workspace.index.add_or_update(new_path, content)
                        except Exception:
                            pass
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not rename: {e}")

    def _delete_file(self, file_path: Path, is_dir: bool) -> None:
        """Löscht eine Datei oder einen Ordner und entfernt sie aus dem Index."""
        target_type = "directory" if is_dir else "file"
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this {target_type}?\n\n{file_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import shutil
                import os
                if is_dir:
                    shutil.rmtree(file_path)
                    # TODO: Rekursiv alle Dateien im Ordner aus dem Index entfernen
                else:
                    os.remove(file_path)
                
                # Aus Index entfernen
                if self._workspace:
                    self._workspace.index.remove(file_path)
                
                # Signal emitten, damit Tabs geschlossen werden können
                if not is_dir:
                    self.file_deleted.emit(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")
