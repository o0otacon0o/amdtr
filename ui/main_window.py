"""
MainWindow — the main window of the application.

Qt Concept: QMainWindow
  QMainWindow is a specialized QWidget with built-in slots for:
    - Menu Bar (top)
    - Toolbars (top/bottom/side, optional)
    - Dock Widgets (dockable side panels, optional)
    - Central Widget (fills the remaining space)
    - Status Bar (bottom)

  We use: Menu Bar + Central Widget + Status Bar.

Qt Concept: QSplitter
  Allows the user to adjust the width of sidebar and editor by dragging
  the divider. setSizes() sets the initial widths in pixels.
  setStretchFactor() determines which widget grows when resizing the window
  (0 = do not stretch, 1 = stretch).

Qt Concept: QSettings
  Persistent settings between program starts.
  On Windows: HKEY_CURRENT_USER\\Software\\amdtr\\app (Registry)
  On macOS/Linux: ~/.config/amdtr/app.conf
  Use setValue() to save, value() to read.
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QLabel, QFileDialog,
    QMessageBox, QWidget, QHBoxLayout, QToolButton,
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QPixmap

from core.workspace import Workspace
from themes.manager import ThemeManager
from themes.schema import Theme


class MainWindow(QMainWindow):

    def __init__(self, version: str = "0.0.0") -> None:
        super().__init__()
        self._version = version
        self._workspace: Workspace | None = None
        self._settings = QSettings("amdtr", "app")
        
        # Deferred import
        from preview.exporter import HTMLExporter
        self._html_exporter = HTMLExporter()
        
        # Theme System
        self._theme_manager = ThemeManager()

        self.setWindowTitle(f"amdtr v{self._version}")
        self.resize(1280, 800)

        self._build_central()
        self._build_menu()
        self._build_status_bar()
        self._build_command_palette()
        self._build_search_palette()
        self._wire_signals()
        
        # Set initial theme
        self._apply_theme(self._theme_manager.active_theme())
        
        # Load Vim mode from settings
        vim_enabled = self._settings.value("editor/vim_mode", False, type=bool)
        self._tabs.set_vim_mode(vim_enabled)
        # Pass empty string if disabled, or "NORMAL" if enabled
        self._update_vim_status("NORMAL" if vim_enabled else "")
        
        # Restore session after a short delay to allow UI to appear first
        QTimer.singleShot(50, self._restore_session)

    def _update_vim_status(self, status_text: str) -> None:
        """Updates the status bar label for Vim mode."""
        if hasattr(self, '_lbl_vim'):
            self._lbl_vim.setText(status_text if status_text else "")

    def _on_about(self) -> None:
        """Shows the about dialog."""
        from main import resource_path
        
        msg = QMessageBox(self)
        msg.setWindowTitle("About amdtr")
        
        logo_path = resource_path("amdtr-logo.png")
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaledToWidth(128, Qt.TransformationMode.SmoothTransformation)
            msg.setIconPixmap(pixmap)
        
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<h3>amdtr — Another Markdown Editor</h3>"
            f"<p>Version {self._version}</p>"
            f"<p>A professional Markdown editor with Mermaid, KaTeX, and live preview.</p>"
            f"<p>© 2026 amdtr contributors</p>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _apply_theme(self, theme: Theme) -> None:
        """Applies the theme to the main window and all sub-components."""
        # 1. Generate global QSS
        qss = f"""
            QMainWindow, QWidget {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border-color: {theme.ui.border};
            }}
            
            QSplitter::handle {{
                background-color: {theme.ui.border};
                width: 1px;
            }}
            
            /* Unified Header Bar (MenuBar as Toolbar) */
            QMenuBar {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border-bottom: 1px solid {theme.ui.border};
                padding: 2px;
            }}
            
            QMenuBar::item {{
                background: transparent;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            
            QMenuBar::item:selected {{
                background-color: {theme.ui.button_bg};
            }}

            /* Action Buttons in MenuBar */
            QMenuBar QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
                margin: 0 2px;
                font-size: 14px;
                color: {theme.ui.sidebar_fg};
            }}
            
            QMenuBar QToolButton:hover {{
                background-color: {theme.ui.button_bg};
            }}
            
            QMenuBar QToolButton:pressed {{
                background-color: {theme.ui.border};
            }}

            /* Sidebar Header Styling */
            #SidebarHeader {{
                background-color: {theme.ui.sidebar_bg};
                border-bottom: 1px solid {theme.ui.border};
            }}
            
            /* Search Palette Styling */
            QLineEdit#SearchInput {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border: 1px solid {theme.ui.border};
                padding: 4px;
            }}
            
            QMenu::item {{
                padding: 4px 20px;
                border-radius: 2px;
            }}
            
            QMenu::item:selected {{
                background-color: {theme.ui.tab_active_bg};
                color: {theme.ui.tab_active_fg};
            }}
        """
        self.setStyleSheet(qss)

        # 2. Inform Sidebar
        self._sidebar.setStyleSheet(f"background-color: {theme.ui.sidebar_bg};")
        self._sidebar.set_theme(theme)

        # 3. Inform TabWidget
        self._tabs.set_theme(theme)

    # ── UI Construction ───────────────────────────────────────────────

    def _build_central(self) -> None:
        """Central area with Splitter: Sidebar | Editor+Preview."""
        from ui.sidebar import Sidebar
        from ui.tab_widget import TabWidget
        
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._sidebar = Sidebar()
        self._tabs = TabWidget()

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._tabs)

        # 1:4 Ratio
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([250, 1000])

        self.setCentralWidget(self._splitter)

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # --- File Menu ---
        file_menu = mb.addMenu("&File")
        
        act_new = QAction("&New File", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._on_new_file)
        file_menu.addAction(act_new)

        act_open = QAction("&Open Workspace...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._on_open_workspace)
        file_menu.addAction(act_open)
        
        file_menu.addSeparator()
        
        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save)
        file_menu.addAction(act_save)

        act_save_all = QAction("Save A&ll", self)
        act_save_all.setShortcut("Ctrl+Shift+S")
        act_save_all.triggered.connect(self._on_save_all)
        file_menu.addAction(act_save_all)

        file_menu.addSeparator()

        act_export = QAction("&Export standalone HTML...", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._on_export_html)
        file_menu.addAction(act_export)

        # --- View Menu ---
        view_menu = mb.addMenu("&View")
        
        act_toggle_sidebar = QAction("Toggle &Sidebar", self)
        act_toggle_sidebar.setShortcut("Ctrl+B")
        act_toggle_sidebar.setCheckable(True)
        act_toggle_sidebar.setChecked(True)
        act_toggle_sidebar.triggered.connect(self._on_toggle_sidebar)
        view_menu.addAction(act_toggle_sidebar)
        self._act_toggle_sidebar = act_toggle_sidebar

        # --- Theme Menu ---
        theme_menu = mb.addMenu("&Theme")
        for theme_name in self._theme_manager.available_themes():
            act_theme = QAction(theme_name, self)
            act_theme.triggered.connect(lambda checked, name=theme_name: self._theme_manager.set_active_theme(name))
            theme_menu.addAction(act_theme)

        # ── Help ──────────────────────────────────────────────────────
        help_menu = mb.addMenu("&Help")
        act_about = QAction("&About amdtr", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

        # --- Right side: Quick access buttons ---
        self._header_buttons = QWidget()
        h_layout = QHBoxLayout(self._header_buttons)
        h_layout.setContentsMargins(0, 0, 10, 0)
        h_layout.setSpacing(2)

        # 1. Sidebar Toggle
        self._btn_sidebar = QToolButton()
        self._btn_sidebar.setText("📁")
        self._btn_sidebar.setToolTip("Toggle Sidebar (Ctrl+B)")
        self._btn_sidebar.clicked.connect(self._on_toggle_sidebar)
        h_layout.addWidget(self._btn_sidebar)

        # 2. New File
        self._btn_new = QToolButton()
        self._btn_new.setText("📄")
        self._btn_new.setToolTip("New File (Ctrl+N)")
        self._btn_new.clicked.connect(self._on_new_file)
        h_layout.addWidget(self._btn_new)

        # 3. View Modes
        h_layout.addSpacing(10)
        self._btn_view_editor = QToolButton()
        self._btn_view_editor.setText("📝")
        self._btn_view_editor.setToolTip("Editor Only")
        self._btn_view_editor.clicked.connect(lambda: self._on_change_view_mode("editor"))
        h_layout.addWidget(self._btn_view_editor)

        self._btn_view_split = QToolButton()
        self._btn_view_split.setText("🌓")
        self._btn_view_split.setToolTip("Split View")
        self._btn_view_split.clicked.connect(lambda: self._on_change_view_mode("split"))
        h_layout.addWidget(self._btn_view_split)

        self._btn_view_preview = QToolButton()
        self._btn_view_preview.setText("👁")
        self._btn_view_preview.setToolTip("Preview Only")
        self._btn_view_preview.clicked.connect(lambda: self._on_change_view_mode("preview"))
        h_layout.addWidget(self._btn_view_preview)

        # 4. Scroll Sync Toggle
        h_layout.addSpacing(10)
        self._btn_sync = QToolButton()
        self._btn_sync.setText("🔗")
        self._btn_sync.setCheckable(True)
        self._btn_sync.setToolTip("Synchronize Scrolling")
        self._btn_sync.clicked.connect(self._on_toggle_scroll_sync)
        h_layout.addWidget(self._btn_sync)

        # 5. Search Button
        h_layout.addSpacing(10)
        self._btn_search = QToolButton()
        self._btn_search.setText("🔍")
        self._btn_search.setToolTip("Search in Workspace (Ctrl+Shift+F)")
        self._btn_search.clicked.connect(self._on_open_search)
        h_layout.addWidget(self._btn_search)

        mb.setCornerWidget(self._header_buttons, Qt.Corner.TopRightCorner)

    def _build_status_bar(self) -> None:
        # addWidget(w, stretch=0): left-aligned, fixed space
        # addPermanentWidget(w):   right-aligned, never displaced
        self._lbl_workspace = QLabel("No workspace open")
        self._lbl_cursor = QLabel("")
        self._lbl_vim = QLabel("")
        self._lbl_vim.setStyleSheet("font-weight: bold; color: #888; margin-right: 10px;")

        sb = self.statusBar()
        sb.addWidget(self._lbl_workspace, 1)
        sb.addPermanentWidget(self._lbl_vim)
        sb.addPermanentWidget(self._lbl_cursor)

    def _build_command_palette(self) -> None:
        from ui.command_palette import CommandPalette
        self._command_palette = CommandPalette(self)
        self._command_palette.action_requested.connect(self._on_command_palette_action)
        self._command_palette.file_requested.connect(self._tabs.open_file)

    def _build_search_palette(self) -> None:
        from ui.search_palette import SearchPalette
        self._search_palette = SearchPalette(self)
        self._search_palette.file_requested.connect(self._tabs.open_file)

    def _wire_signals(self) -> None:
        # Sidebar informs when the user double-clicks a file
        self._sidebar.file_activated.connect(self._tabs.open_file)
        self._sidebar.file_deleted.connect(self._on_file_deleted)
        
        # Outline Integration
        self._tabs.active_file_changed.connect(self._sidebar.outline.update_outline)

        # Tab widget informs when the active file changes (to update title)
        self._tabs.active_file_changed.connect(self._on_active_file_changed)
        
        # Tab widget informs when dirty state changes
        self._tabs.dirty_state_changed.connect(self._on_dirty_state_changed)
        self._tabs.vim_status_changed.connect(self._update_vim_status)

        # Command Palette signals
        # (Already connected in _build_command_palette)

        # Theme System signals
        self._theme_manager.theme_changed.connect(self._apply_theme)

    # ── Handlers & Logic ──────────────────────────────────────────────

    def _load_workspace(self, path: Path) -> None:
        """Loads a folder as workspace."""
        try:
            self._workspace = Workspace(path)
            self._sidebar.set_workspace(self._workspace)
            self._lbl_workspace.setText(f"Workspace: {self._workspace.root}")
            self._settings.setValue("last_workspace", str(path))
            
            # Start background indexing
            self._update_search_index()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _update_search_index(self) -> None:
        """Updates the search index in a background thread."""
        if not self._workspace:
            return

        class IndexWorker(QThread):
            finished = pyqtSignal()

            def __init__(self, workspace: Workspace):
                super().__init__()
                self.workspace = workspace

            def run(self):
                print(f"[*] Starting background indexing for {self.workspace.name}...")
                notes = self.workspace.all_notes()
                batch = []
                count = 0
                
                for note_path in notes:
                    try:
                        # 1. Skip if file hasn't changed
                        mtime = note_path.stat().st_mtime
                        if self.workspace.index.get_indexed_mtime(note_path) >= mtime:
                            continue
                            
                        # 2. Add to batch
                        content = note_path.read_text(encoding="utf-8")
                        batch.append((note_path, content))
                        count += 1
                        
                        # Commit in smaller chunks if the workspace is massive
                        if len(batch) >= 100:
                            self.workspace.index.batch_add(batch)
                            batch = []
                    except Exception:
                        pass
                
                # Final commit
                if batch:
                    self.workspace.index.batch_add(batch)
                
                if count > 0:
                    print(f"[+] Re-indexed {count} changed files.")
                else:
                    print("[+] Workspace is up to date.")
                self.finished.emit()

        from PyQt6.QtCore import QThread
        self._index_thread = IndexWorker(self._workspace)
        self._index_thread.finished.connect(lambda: self.statusBar().showMessage("Search index updated", 3000))
        self._index_thread.start()

    def _on_open_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Workspace Folder")
        if path:
            self._load_workspace(Path(path))

    def _on_open_file(self) -> None:
        """Opens a file via standard dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Markdown Files (*.md *.mmd *.txt)"
        )
        if path:
            self._tabs.open_file(Path(path))

    def _on_new_file(self) -> None:
        """Creates a new file with immediate save dialog."""
        path, _ = QFileDialog.getSaveFileName(
            self, "New File", "", "Markdown Files (*.md)"
        )
        if path:
            p = Path(path)
            p.write_text("", encoding="utf-8")
            self._tabs.open_file(p)
            self._sidebar.refresh()

    def _on_save(self) -> None:
        self._tabs.save_current()

    def _on_save_all(self) -> None:
        self._tabs.save_all()

    def _on_export_html(self) -> None:
        active_editor = self._tabs.current_editor()
        if not active_editor:
            QMessageBox.information(self, "Export", "No file open to export.")
            return

        target_path, _ = QFileDialog.getSaveFileName(
            self, "Export standalone HTML", "", "HTML Files (*.html)"
        )
        
        if target_path:
            success = self._html_exporter.export(
                active_editor.path(),
                Path(target_path)
            )
            if success:
                self.statusBar().showMessage(f"Exported to {target_path}", 5000)

    def _on_toggle_sidebar(self) -> None:
        visible = not self._sidebar.isVisible()
        self._sidebar.setVisible(visible)
        self._act_toggle_sidebar.setChecked(visible)

    def _on_change_view_mode(self, mode: str) -> None:
        active_editor = self._tabs.current_editor()
        if active_editor:
            active_editor.set_view_mode(mode)

    def _on_toggle_scroll_sync(self) -> None:
        active_editor = self._tabs.current_editor()
        if active_editor:
            active_editor.set_scroll_sync(self._btn_sync.isChecked())

    def _on_open_search(self) -> None:
        self._search_palette.show_palette()

    def _on_command_palette_action(self, action_name: str) -> None:
        """Executes an action from the Command Palette."""
        if action_name == "open_workspace":
            self._on_open_workspace()
        elif action_name == "open_file":
            self._on_open_file()
        elif action_name == "save_all":
            self._on_save_all()
        elif action_name == "toggle_sidebar":
            self._on_toggle_sidebar()
        elif action_name == "toggle_vim":
            self._on_toggle_vim_mode()

    def _on_toggle_vim_mode(self) -> None:
        """Toggles Vim modal editing and saves the preference."""
        enabled = not self._settings.value("editor/vim_mode", False, type=bool)
        self._settings.setValue("editor/vim_mode", enabled)
        self._tabs.set_vim_mode(enabled)
        # Pass "NORMAL" or empty string
        self._update_vim_status("NORMAL" if enabled else "")
        self.statusBar().showMessage(f"Vim Mode {'Enabled' if enabled else 'Disabled'}", 3000)

    def _on_active_file_changed(self, path: Path | None) -> None:
        self._update_title()

    def _on_dirty_state_changed(self) -> None:
        self._update_title()

    def _update_title(self) -> None:
        base = "amdtr"
        if self._workspace:
            base = f"amdtr — {self._workspace.name}"
        
        active_file = self._tabs.active_file()
        if active_file:
            dirty_star = "*" if self._tabs.is_current_dirty() else ""
            self.setWindowTitle(f"{active_file.name}{dirty_star} — {base} v{self._version}")
        else:
            self.setWindowTitle(f"{base} v{self._version}")

    def _on_file_deleted(self, path: Path) -> None:
        """Called when a file has been deleted in the sidebar."""
        # Check if file is open in a tab
        if path in self._tabs._open_paths:
            idx = self._tabs._open_paths[path]
            self._tabs.removeTab(idx)
        
        # Remove from index
        if self._workspace:
            self._workspace.index.add_or_update(path, "") # Effectively clears content

    def _restore_session(self) -> None:
        """Restores previous workspace and open files."""
        # 1. Geometry
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

        split_state = self._settings.value("splitter_state")
        if split_state:
            self._splitter.restoreState(split_state)

        # 2. Workspace
        last_ws = self._settings.value("last_workspace")
        if last_ws:
            p = Path(str(last_ws))
            if p.exists():
                self._load_workspace(p)
                self._sidebar.show()
            else:
                self._sidebar.hide()
        else:
            self._sidebar.hide()

    def closeEvent(self, event) -> None:
        """Save session on close."""
        # Check for unsaved changes
        if self._tabs.has_dirty_tabs():
            res = QMessageBox.question(
                self, "Unsaved Changes",
                "Some files have unsaved changes. Save them now?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if res == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if res == QMessageBox.StandardButton.Save:
                self._tabs.save_all()

        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter_state", self._splitter.saveState())
        event.accept()
