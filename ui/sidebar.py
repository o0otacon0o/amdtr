"""
Sidebar — file tree + search/filter.

Qt Concept: Model/View Architecture
  Qt separates data (Model) from its representation (View).
  QFileSystemModel = the Model (reads the file system)
  QTreeView         = the View (shows tree structure)
  QSortFilterProxyModel = sits between Model and View,
    filters/sorts without modifying the original Model.

  Advantage: the same data can be displayed by multiple views,
  and sorting/filtering does not require reloading.

Qt Concept: pyqtSignal
  Custom signals are declared as class attributes with pyqtSignal().
  Each instance gets its own copy.
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
    """
    Proxy model with recursive filter:
    A folder is displayed if at least one child matches the filter.

    Without this override, folders would be hidden when a filter is active
    — the tree would collapse and no files could be seen.
    """

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # No active filter → show everything
        if not self.filterRegularExpression().pattern():
            return True

        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)

        # For directories: show if any child matches
        if model.isDir(index):
            for i in range(model.rowCount(index)):
                if self.filterAcceptsRow(i, index):
                    return True
            return False

        # For files: standard filter (filename match)
        return super().filterAcceptsRow(source_row, source_parent)


class Sidebar(QWidget):
    """
    Left panel: workspace header + search bar + file tree/outline.

    Signals:
      file_activated(Path)          — User double-clicks a file
      open_workspace_requested(Path) — User clicks "…" and selects a folder
      outline_item_clicked(int)      — User clicks a header in the outline
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

        # Model: represents the file system
        self._fs_model = QFileSystemModel()
        self._fs_model.setReadOnly(False)

        # Proxy: sits in front of the model, handles filtering and sorting
        self._proxy = _RecursiveFilterProxy()
        self._proxy.setSourceModel(self._fs_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────

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
        frame.setObjectName("SidebarHeader")
        frame.setFixedHeight(40)

        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 0, 8, 0)
        h.setSpacing(4)

        self._lbl_workspace = QLabel("NO WORKSPACE")
        self._lbl_workspace.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._lbl_workspace.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        btn_open = QToolButton()
        btn_open.setText("…")
        btn_open.setToolTip("Open workspace folder (Ctrl+Shift+O)")
        btn_open.setFixedSize(24, 24)
        btn_open.clicked.connect(self._on_open_btn_clicked)

        h.addWidget(self._lbl_workspace)
        h.addWidget(btn_open)
        return frame

    def _build_search(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(38)
        h = QHBoxLayout(container)
        h.setContentsMargins(10, 6, 10, 6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter files…")
        self._search_input.setClearButtonEnabled(True)

        self._search_input.textChanged.connect(self._on_filter_changed)

        h.addWidget(self._search_input)
        return container

    # ── Public API ────────────────────────────────────────────────────

    @property
    def outline(self) -> OutlinePanel:
        """Access to the outline panel."""
        return self._outline

    def set_theme(self, theme: Theme) -> None:
        """Applies theme colors to the sidebar components."""
        # Header
        self.setStyleSheet(f"""
            #SidebarHeader {{
                background-color: {theme.ui.sidebar_bg};
                border-bottom: 1px solid {theme.ui.border};
            }}
            QLabel {{
                color: {theme.ui.sidebar_fg};
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {theme.ui.sidebar_fg};
            }}
            QToolButton:hover {{
                background-color: {theme.ui.button_bg};
            }}
        """)

        # 1. Tree View
        self._tree.setStyleSheet(f"""
            QTreeView {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border: none;
                padding: 4px;
            }}
            QTreeView::item {{
                padding: 4px;
                border-radius: 4px;
            }}
            QTreeView::item:hover {{
                background-color: {theme.ui.button_bg};
            }}
            QTreeView::item:selected {{
                background-color: {theme.ui.tab_active_bg};
                color: {theme.preview.link};
                font-weight: bold;
            }}
        """)
        
        # 2. Search input
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.ui.button_bg};
                color: {theme.ui.sidebar_fg};
                border: 1px solid {theme.ui.border};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {theme.preview.link};
            }}
        """)
        
        # 3. Tab Widget (Sidebar Bottom Tabs)
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border-top: 1px solid {theme.ui.border};
                background-color: {theme.ui.sidebar_bg};
            }}
            QTabBar::tab {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.tab_inactive_fg};
                padding: 6px 12px;
                min-width: 60px;
                font-size: 11px;
                border: none;
            }}
            QTabBar::tab:selected {{
                color: {theme.preview.link};
                border-top: 2px solid {theme.preview.link};
                background-color: {theme.ui.tab_active_bg};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {theme.ui.button_bg};
            }}
        """)
        
        # 4. Outline Panel
        self._outline.set_theme(theme)

    def set_workspace(self, ws: Workspace | None) -> None:
        """Called by MainWindow when a workspace is opened or closed."""
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

        # setRootPath starts monitoring the directory.
        self._fs_model.setRootPath(str(ws.root))
        
        # Show only note files.
        self._fs_model.setNameFilters(["*.md", "*.mmd", "*.txt"])
        self._fs_model.setNameFilterDisables(False)

        # IMPORTANT: Set the root index for the view.
        # Since we use a proxy, we must map the index.
        source_index = self._fs_model.index(str(ws.root))
        proxy_index = self._proxy.mapFromSource(source_index)
        self._tree.setRootIndex(proxy_index)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_item_activated(self, proxy_index: QModelIndex) -> None:
        # Proxy Index → Source Index → File Path
        source_index = self._proxy.mapToSource(proxy_index)

        if self._fs_model.isDir(source_index):
            return  # Don't open folders, only files

        path = Path(self._fs_model.filePath(source_index))
        self.file_activated.emit(path)

    def _on_filter_changed(self, text: str) -> None:
        # setFilterFixedString: searches for exact substring (case-insensitive
        # because we set setFilterCaseSensitivity)
        self._proxy.setFilterFixedString(text)

        if text:
            # When filter is active: expand entire tree so matches are visible
            self._tree.expandAll()
        else:
            # Filter cleared: collapse tree again
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
        """Creates and shows the context menu for files/folders."""
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return

        source_index = self._proxy.mapToSource(index)
        file_path = Path(self._fs_model.filePath(source_index))
        is_dir = self._fs_model.isDir(source_index)

        menu = QMenu(self)
        
        # Define actions
        rename_act = menu.addAction("Rename")
        delete_act = menu.addAction("Delete")
        
        # Show menu and catch selected action
        action = menu.exec(self._tree.mapToGlobal(pos))
        
        if action == rename_act:
            self._rename_file(source_index, file_path)
        elif action == delete_act:
            self._delete_file(file_path, is_dir)

    def _rename_file(self, source_index: QModelIndex, old_path: Path) -> None:
        """Renames a file or folder and updates the index."""
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", QLineEdit.EchoMode.Normal, old_path.name
        )
        
        if ok and new_name and new_name != old_path.name:
            new_path = old_path.parent / new_name
            try:
                import os
                os.rename(old_path, new_path)
                
                # Update index
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
        """Deletes a file or folder and removes it from the index."""
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
                    # TODO: Recursively remove all files in folder from index
                else:
                    os.remove(file_path)
                
                # Remove from index
                if self._workspace:
                    self._workspace.index.remove(file_path)
                
                # Emit signal so tabs can be closed
                if not is_dir:
                    self.file_deleted.emit(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")
