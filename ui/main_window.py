"""
MainWindow — das Hauptfenster der Anwendung.

Qt-Konzept: QMainWindow
  QMainWindow ist ein spezialisiertes QWidget mit eingebauten Slots für:
    - Menu Bar (oben)
    - Toolbars (oben/unten/seitlich, optional)
    - Dock Widgets (andockbare Seitenpanels, optional)
    - Central Widget (füllt den verbleibenden Platz)
    - Status Bar (unten)

  Wir nutzen: Menu Bar + Central Widget + Status Bar.

Qt-Konzept: QSplitter
  Erlaubt dem User, die Breite von Sidebar und Editor durch Ziehen
  der Trennlinie anzupassen. setSizes() setzt die Anfangsbreiten in Pixel.
  setStretchFactor() bestimmt, welches Widget beim Vergrößern des Fensters
  wächst (0 = nicht strecken, 1 = strecken).

Qt-Konzept: QSettings
  Persistente Einstellungen zwischen Programmstarts.
  Auf Windows: HKEY_CURRENT_USER\\Software\\amdtr\\app (Registry)
  Auf macOS/Linux: ~/.config/amdtr/app.conf
  Nutze setValue() zum Speichern, value() zum Lesen.
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QLabel, QFileDialog,
    QMessageBox, QWidget, QHBoxLayout, QToolButton,
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence

from core.workspace import Workspace
from preview.exporter import HTMLExporter
from ui.sidebar import Sidebar
from ui.tab_widget import TabWidget
from ui.command_palette import CommandPalette
from ui.search_palette import SearchPalette
from ui.editor_preview_split import EditorPreviewSplit
from themes.manager import ThemeManager
from themes.schema import Theme


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self._workspace: Workspace | None = None
        self._settings = QSettings("amdtr", "app")
        self._html_exporter = HTMLExporter()
        
        # Theme System
        self._theme_manager = ThemeManager()

        self.setWindowTitle("amdtr")
        self.resize(1280, 800)

        self._build_central()
        self._build_menu()
        self._build_status_bar()
        self._build_command_palette()
        self._build_search_palette()
        self._wire_signals()
        
        # Initial Theme setzen
        self._apply_theme(self._theme_manager.active_theme())
        
        self._restore_session()

    def _apply_theme(self, theme: Theme) -> None:
        """Wendet das Theme auf das Hauptfenster und alle Sub-Komponenten an."""
        # 1. Globale QSS generieren
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
                background-color: {theme.ui.tab_active_bg};
            }}

            QMenuBar QToolButton:checked {{
                background-color: {theme.ui.tab_active_bg};
                border: 1px solid {theme.preview.link};
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border-top: 1px solid {theme.ui.border};
                background-color: {theme.editor.background};
            }}
            
            QTabBar::tab {{
                background-color: {theme.ui.tab_inactive_bg};
                color: {theme.ui.tab_inactive_fg};
                padding: 6px 16px;
                border-right: 1px solid {theme.ui.border};
                font-size: 11px;
                min-width: 120px;
                max-width: 250px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {theme.ui.tab_active_bg};
                color: {theme.ui.tab_active_fg};
                border-bottom: 2px solid {theme.preview.link};
            }}
            
            /* Sidebar Tree */
            QTreeView {{
                background-color: {theme.ui.sidebar_bg};
                border: none;
                outline: none;
            }}
            
            QTreeView::item {{
                padding: 4px;
            }}
            
            QTreeView::item:selected {{
                background-color: {theme.ui.button_bg};
                color: {theme.ui.sidebar_fg};
            }}
            
            /* Input Fields */
            QLineEdit {{
                background-color: {theme.ui.tab_active_bg};
                border: 1px solid {theme.ui.border};
                border-radius: 4px;
                padding: 4px 8px;
                color: {theme.ui.sidebar_fg};
            }}
            
            /* Status Bar */
            QStatusBar {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border-top: 1px solid {theme.ui.border};
                font-size: 11px;
            }}
            
            QLabel {{
                background: transparent;
            }}
            
            /* Menu Bar Dropdowns */
            QMenu {{
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
                background-color: {theme.ui.button_bg};
            }}
            
            /* Standard Buttons */
            QToolButton {{
                background-color: {theme.ui.button_bg};
                border: 1px solid {theme.ui.border};
                border-radius: 4px;
                color: {theme.ui.button_fg};
            }}
            
            QToolButton:hover {{
                background-color: {theme.ui.tab_active_bg};
            }}
        """
        self.setStyleSheet(qss)
        
        # 2. Sidebar informieren
        self._sidebar.setStyleSheet(f"background-color: {theme.ui.sidebar_bg}; color: {theme.ui.sidebar_fg}; border-right: 1px solid {theme.ui.border};")
        
        # 3. Tabs informieren
        self._tabs.set_theme(theme)

    # ── UI construction ───────────────────────────────────────────────

    def _build_central(self) -> None:
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)

        self._sidebar = Sidebar()
        self._tabs = TabWidget()

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._tabs)

        # Index 0 = Sidebar: nicht strecken beim Fenster-Resize
        # Index 1 = Editor:  strecken (nimmt verfügbaren Platz)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 1020])

        # Das Central Widget füllt den gesamten Bereich zwischen
        # Menu Bar und Status Bar.
        self.setCentralWidget(self._splitter)

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        file_menu = mb.addMenu("&File")

        act_open_ws = QAction("Open &Workspace…", self)
        act_open_ws.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_ws.setStatusTip("Open a folder as workspace")
        act_open_ws.triggered.connect(self._on_open_workspace)
        file_menu.addAction(act_open_ws)

        act_close_ws = QAction("&Close Workspace", self)
        act_close_ws.setStatusTip("Close the current workspace")
        act_close_ws.triggered.connect(self._on_close_workspace)
        file_menu.addAction(act_close_ws)

        act_open_file = QAction("&Open File…", self)
        act_open_file.setShortcut(QKeySequence.StandardKey.Open)
        act_open_file.setStatusTip("Open a single markdown file")
        act_open_file.triggered.connect(self._on_open_file)
        file_menu.addAction(act_open_file)

        file_menu.addSeparator()

        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save)
        file_menu.addAction(act_save)

        act_save_all = QAction("Save A&ll", self)
        act_save_all.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_all.triggered.connect(self._on_save_all)
        file_menu.addAction(act_save_all)

        file_menu.addSeparator()

        act_export_html = QAction("Export as &HTML…", self)
        act_export_html.setShortcut(QKeySequence("Ctrl+Shift+E"))
        act_export_html.setStatusTip("Export current file as standalone HTML")
        act_export_html.triggered.connect(self._on_export_html)
        file_menu.addAction(act_export_html)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── View ──────────────────────────────────────────────────────
        view_menu = mb.addMenu("&View")

        act_toggle_sidebar = QAction("Toggle &Sidebar", self)
        act_toggle_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        act_toggle_sidebar.triggered.connect(self._on_toggle_sidebar)
        view_menu.addAction(act_toggle_sidebar)

        act_toggle_preview = QAction("Toggle &Preview", self)
        act_toggle_preview.setShortcut(QKeySequence("Ctrl+Alt+P"))
        act_toggle_preview.setStatusTip("Toggle the live preview panel")
        act_toggle_preview.triggered.connect(self._on_toggle_preview)
        view_menu.addAction(act_toggle_preview)

        act_global_search = QAction("Global &Search", self)
        act_global_search.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_global_search.setStatusTip("Search in all files in workspace")
        act_global_search.triggered.connect(self._on_global_search)
        view_menu.addAction(act_global_search)

        view_menu.addSeparator()

        # Command Palette
        act_command_palette = QAction("Command &Palette…", self)
        act_command_palette.setShortcut(QKeySequence("Ctrl+P"))
        act_command_palette.setStatusTip("Quick open files and commands")
        act_command_palette.triggered.connect(self._on_command_palette)
        view_menu.addAction(act_command_palette)

        act_command_palette_actions = QAction("Command Palette (&Actions Only)…", self)
        act_command_palette_actions.setShortcut(QKeySequence("Ctrl+Shift+P"))
        act_command_palette_actions.setStatusTip("Show actions only")
        act_command_palette_actions.triggered.connect(self._on_command_palette_actions)
        view_menu.addAction(act_command_palette_actions)

        # ── Theme ─────────────────────────────────────────────────────
        theme_menu = mb.addMenu("&Theme")
        
        # Dynamisch alle verfügbaren Themes laden
        for theme_name in self._theme_manager.get_theme_names():
            act_theme = QAction(theme_name, self)
            act_theme.triggered.connect(lambda checked, name=theme_name: self._theme_manager.set_active_theme(name))
            theme_menu.addAction(act_theme)

        # --- Rechte Seite: Schnellzugriff-Buttons ---
        self._header_buttons = QWidget()
        h_layout = QHBoxLayout(self._header_buttons)
        h_layout.setContentsMargins(0, 0, 10, 0)
        h_layout.setSpacing(2)

        # 1. Sidebar Toggle
        self._btn_sidebar = QToolButton()
        self._btn_sidebar.setText("📁")
        self._btn_sidebar.setCheckable(True)
        self._btn_sidebar.setChecked(True)
        self._btn_sidebar.setToolTip("Toggle Sidebar (Ctrl+B)")
        self._btn_sidebar.clicked.connect(self._on_toggle_sidebar)
        
        # 2. New File
        self._btn_new = QToolButton()
        self._btn_new.setText("➕")
        self._btn_new.setToolTip("New File (Ctrl+N)")
        self._btn_new.clicked.connect(self._on_new_file)

        # 3. View Modes (Segmented Control Stil)
        self._btn_view_editor = QToolButton()
        self._btn_view_editor.setText("📝")
        self._btn_view_editor.setCheckable(True)
        self._btn_view_editor.setToolTip("Editor Only")
        self._btn_view_editor.clicked.connect(lambda: self._on_set_view_mode('editor'))

        self._btn_view_split = QToolButton()
        self._btn_view_split.setText("🌓")
        self._btn_view_split.setCheckable(True)
        self._btn_view_split.setToolTip("Split View")
        self._btn_view_split.clicked.connect(lambda: self._on_set_view_mode('split'))

        self._btn_view_preview = QToolButton()
        self._btn_view_preview.setText("👁️")
        self._btn_view_preview.setCheckable(True)
        self._btn_view_preview.setToolTip("Preview Only")
        self._btn_view_preview.clicked.connect(lambda: self._on_set_view_mode('preview'))

        # 3.5 Scroll Sync Toggle
        self._btn_sync = QToolButton()
        self._btn_sync.setText("🔗")
        self._btn_sync.setCheckable(True)
        self._btn_sync.setChecked(False)
        self._btn_sync.setToolTip("Toggle Scroll Sync")
        self._btn_sync.clicked.connect(self._on_toggle_scroll_sync)

        # 4. Find in Document
        self._btn_find = QToolButton()
        self._btn_find.setText("🔎")
        self._btn_find.setToolTip("Find in Document (Ctrl+F)")
        self._btn_find.clicked.connect(self._on_find_in_document)

        # 5. Global Search (FTS5)
        self._btn_global_search = QToolButton()
        self._btn_global_search.setText("🌍")
        self._btn_global_search.setToolTip("Global Search (Ctrl+Shift+F)")
        self._btn_global_search.clicked.connect(self._on_global_search)

        # 6. Command Palette
        self._btn_search = QToolButton()
        self._btn_search.setText("🔍")
        self._btn_search.setToolTip("Command Palette (Ctrl+P)")
        self._btn_search.clicked.connect(self._on_command_palette)

        # 7. HTML Export
        self._btn_export = QToolButton()
        self._btn_export.setText("📤")
        self._btn_export.setToolTip("Export as HTML (Ctrl+Shift+E)")
        self._btn_export.clicked.connect(self._on_export_html)

        h_layout.addWidget(self._btn_sidebar)
        h_layout.addWidget(self._btn_view_editor)
        h_layout.addWidget(self._btn_view_split)
        h_layout.addWidget(self._btn_view_preview)
        h_layout.addWidget(self._btn_sync)
        h_layout.addWidget(self._btn_find)
        h_layout.addWidget(self._btn_global_search)
        h_layout.addWidget(self._btn_search)
        h_layout.addWidget(self._btn_export)
        h_layout.addWidget(self._btn_new)

        mb.setCornerWidget(self._header_buttons, Qt.Corner.TopRightCorner)

    def _build_status_bar(self) -> None:
        # addWidget(w, stretch=0): links ausgerichtet, fester Platz
        # addPermanentWidget(w):   rechts ausgerichtet, verdrängt nie andere
        self._lbl_workspace = QLabel("No workspace open")
        self._lbl_cursor = QLabel("")

        sb = self.statusBar()
        sb.addWidget(self._lbl_workspace, 1)
        sb.addPermanentWidget(self._lbl_cursor)

    def _build_command_palette(self) -> None:
        """Erstellt und konfiguriert die Command Palette."""
        self._command_palette = CommandPalette(self)

    def _build_search_palette(self) -> None:
        """Erstellt das Overlay für die Volltextsuche."""
        self._search_palette = SearchPalette(self)

    # ── Signal wiring ─────────────────────────────────────────────────
    #
    # Qt-Konzept: Signals & Slots
    #   signal.connect(slot) verbindet ein Signal mit einem Callable.
    #   Wenn das Signal emittet wird, ruft Qt alle verbundenen Slots auf.
    #   Ein Signal kann mit beliebig vielen Slots verbunden sein.
    #   Slots können beliebige Python-Callables sein (Methoden, Lambdas, …).

    def _wire_signals(self) -> None:
        # Sidebar teilt mit wenn der User auf eine Datei doppelklickt
        self._sidebar.file_activated.connect(self._tabs.open_file)
        self._sidebar.file_deleted.connect(self._on_file_deleted)
        
        # Outline Integration
        self._sidebar.outline_item_clicked.connect(self._on_outline_item_clicked)

        # Sidebar-Button "…" möchte Workspace wechseln
        self._sidebar.open_workspace_requested.connect(self._load_workspace)

        # Tab-Widget teilt mit welche Datei gerade aktiv ist
        self._tabs.active_file_changed.connect(self._on_active_file_changed)
        self._tabs.currentChanged.connect(self._update_outline) # Bei Tab-Wechsel

        # Tab-Widget teilt mit wenn sich der Dirty-State ändert
        self._tabs.dirty_state_changed.connect(self._on_dirty_state_changed)

        # Command Palette Signals
        self._command_palette.file_requested.connect(self._tabs.open_file)
        self._command_palette.action_requested.connect(self._on_command_palette_action)
        
        # Global Search Signals
        self._search_palette.file_requested.connect(self._tabs.open_file)
        
        # Theme Signals
        self._theme_manager.theme_changed.connect(self._apply_theme)

    def _on_outline_item_clicked(self, line: int) -> None:
        """Scrollt den aktiven Editor zur angegebenen Zeile."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            w.editor().set_cursor_position(line, 0)
            w.editor().setFocus()

    def _update_outline(self) -> None:
        """Aktualisiert die Gliederung basierend auf dem aktuellen Dokument."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            self._sidebar._outline.update_outline(w.toPlainText())
        else:
            self._sidebar._outline.update_outline("")

    # ── Slots: Menu-Aktionen ──────────────────────────────────────────

    def _on_open_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Open Workspace",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._load_workspace(Path(path))

    def _on_close_workspace(self) -> None:
        """Schließt den aktuellen Workspace und setzt die UI zurück."""
        if not self._workspace:
            return

        # Optional: Alle Tabs schließen?
        # self._tabs.clear() 
        # (Meistens behält man die Tabs offen, aber sie sind nicht mehr Teil des WS)

        self._workspace = None
        self._sidebar.set_workspace(None)
        self._sidebar.hide()
        self._command_palette.set_workspace(None)
        self._search_palette.set_workspace(None)
        self._tabs.set_workspace(None)
        
        self.setWindowTitle("amdtr")
        self._lbl_workspace.setText("No workspace open")
        self._settings.remove("last_workspace")
        
        print("[*] Workspace closed.")

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File",
            str(Path.home()),
            "Markdown (*.md *.mmd);;Text (*.txt);;All files (*.*)",
        )
        if path:
            self._tabs.open_file(Path(path))

    def _on_save(self) -> None:
        self._tabs.save_current()
        # Index aktualisieren
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit) and self._workspace:
            self._workspace.index.add_or_update(w.path(), w.toPlainText())

    def _on_save_all(self) -> None:
        self._tabs.save_all()
        # Alle offenen Dateien im Index aktualisieren
        if self._workspace:
            for i in range(self._tabs.count()):
                w = self._tabs.widget(i)
                if isinstance(w, EditorPreviewSplit):
                    self._workspace.index.add_or_update(w.path(), w.toPlainText())

    def _on_file_deleted(self, path: Path) -> None:
        """Wird aufgerufen wenn eine Datei in der Sidebar gelöscht wurde."""
        # Prüfen ob die Datei in einem Tab offen ist
        if path in self._tabs._open_paths:
            idx = self._tabs._open_paths[path]
            # Tab ohne Speichern-Frage schließen (Datei ist ja schon weg)
            self._tabs.removeTab(idx)
            self._tabs._rebuild_path_index()

    def _on_new_file(self) -> None:
        """Fragt nach einem Speicherort und erstellt eine neue Markdown-Datei."""
        # Standard-Pfad: Workspace oder Home
        initial_dir = self._workspace.root if self._workspace else Path.home()
        
        # Dialog zum Speichern öffnen
        file_path_str, _ = QFileDialog.getSaveFileName(
            self, "Create New Markdown File",
            str(initial_dir / "Untitled.md"),
            "Markdown (*.md *.mmd);;Text (*.txt);;All files (*.*)"
        )
        
        if not file_path_str:
            return # User hat abgebrochen

        file_path = Path(file_path_str)
            
        try:
            # Leere Datei erstellen (falls sie noch nicht existiert)
            if not file_path.exists():
                file_path.write_text("", encoding="utf-8")
            
            # Datei öffnen
            self._tabs.open_file(file_path)
            
            # Fokus auf den Editor setzen
            w = self._tabs.currentWidget()
            if isinstance(w, EditorPreviewSplit):
                w.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create file: {e}")

    def _on_toggle_sidebar(self) -> None:
        is_visible = not self._sidebar.isVisible()
        self._sidebar.setVisible(is_visible)
        if hasattr(self, '_btn_sidebar'):
            self._btn_sidebar.setChecked(is_visible)

    def _on_find_in_document(self) -> None:
        """Triggert die Suche im aktuellen Editor (Ctrl+F)."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            w.act_find.trigger()

    def _on_command_palette(self) -> None:
        """Öffnet Command Palette für Dateien und Aktionen (Ctrl+P)."""
        self._command_palette.show_files_and_actions()

    def _on_global_search(self) -> None:
        """Öffnet die globale Volltextsuche (Ctrl+Shift+F)."""
        if self._workspace:
            self._search_palette.open_search()
        else:
            QMessageBox.information(self, "Global Search", "Please open a workspace first.")

    def _on_command_palette_actions(self) -> None:
        """Öffnet Command Palette nur für Aktionen (Ctrl+Shift+P)."""
        self._command_palette.show_actions_only()

    def _on_command_palette_action(self, action_name: str) -> None:
        """Führt eine Aktion aus der Command Palette aus."""
        if action_name == "open_workspace":
            self._on_open_workspace()
        elif action_name == "open_file":
            self._on_open_file()
        elif action_name == "save_all":
            self._on_save_all()
        elif action_name == "toggle_sidebar":
            self._on_toggle_sidebar()

    def _on_export_html(self) -> None:
        """Exportiert die aktuelle Datei als HTML."""
        w = self._tabs.currentWidget()
        if not isinstance(w, EditorPreviewSplit):
            QMessageBox.information(self, "Export", "No active document to export.")
            return

        markdown = w.toPlainText()
        default_name = w.path().with_suffix(".html").name
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML",
            str(Path.home() / default_name),
            "HTML Files (*.html)"
        )
        
        if path:
            success = self._html_exporter.export(markdown, Path(path), title=w.path().stem)
            if success:
                self.statusBar().showMessage(f"Exported to {path}", 5000)
            else:
                QMessageBox.critical(self, "Export Error", "Failed to export HTML.")

    def _on_toggle_preview(self) -> None:
        """Klassischer Toggle (wird von QAction genutzt)."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            w.toggle_preview()
            self._update_view_mode_buttons(w.get_view_mode())

    def _on_set_view_mode(self, mode: str) -> None:
        """Setzt den Ansichtsmodus im aktuellen Tab."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            w.set_view_mode(mode)
            self._update_view_mode_buttons(mode)

    def _update_view_mode_buttons(self, mode: str) -> None:
        """Aktualisiert den checked-Status der 3 View-Mode Buttons."""
        if not hasattr(self, '_btn_view_editor'):
            return
            
        self._btn_view_editor.setChecked(mode == 'editor')
        self._btn_view_split.setChecked(mode == 'split')
        self._btn_view_preview.setChecked(mode == 'preview')

    def _on_toggle_scroll_sync(self) -> None:
        """Schaltet den Scroll-Sync im aktuellen Tab um."""
        w = self._tabs.currentWidget()
        if isinstance(w, EditorPreviewSplit):
            is_enabled = not w.is_scroll_sync_enabled()
            w.set_scroll_sync_enabled(is_enabled)
            if hasattr(self, '_btn_sync'):
                self._btn_sync.setChecked(is_enabled)

    # ── Slots: von anderen Widgets ────────────────────────────────────

    def _on_active_file_changed(self, path: Path | None) -> None:
        # Button-Status an den aktuellen Tab anpassen
        w = self._tabs.currentWidget()
        is_split = isinstance(w, EditorPreviewSplit)
        
        if is_split:
            # Signal für Gliederungs-Update verknüpfen
            try:
                w.content_changed.disconnect(self._update_outline)
            except TypeError:
                pass
            w.content_changed.connect(self._update_outline)
            
            # Initiales Update
            self._update_outline()
            
            # View Mode Buttons aktualisieren
            self._update_view_mode_buttons(w.get_view_mode())

        if hasattr(self, '_btn_sync'):
            self._btn_sync.setEnabled(is_split)
            if is_split:
                self._btn_sync.setChecked(w.is_scroll_sync_enabled())
            else:
                self._btn_sync.setChecked(False)

        if hasattr(self, '_btn_find'):
            self._btn_find.setEnabled(is_split)

        if hasattr(self, '_btn_global_search'):
            self._btn_global_search.setEnabled(self._workspace is not None)

        if hasattr(self, '_btn_export'):
            self._btn_export.setEnabled(is_split)
        if path:
            ws_part = ""
            if self._workspace:
                try:
                    ws_part = str(path.relative_to(self._workspace.root))
                except ValueError:
                    ws_part = path.name
            else:
                ws_part = path.name
            self._lbl_workspace.setText(ws_part)
        else:
            self._lbl_workspace.setText(
                str(self._workspace.root) if self._workspace else "No workspace open"
            )

    def _on_dirty_state_changed(self) -> None:
        # Fenster-Titel zeigt "●" wenn es ungespeicherte Änderungen gibt
        base = "amdtr"
        if self._workspace:
            base = f"amdtr — {self._workspace.name}"
        if self._tabs.has_unsaved_changes():
            self.setWindowTitle(f"● {base}")
        else:
            self.setWindowTitle(base)

    # ── Workspace laden ───────────────────────────────────────────────

    def _load_workspace(self, path: Path) -> None:
        try:
            ws = Workspace(path)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Workspace", str(e))
            return

        self._workspace = ws
        self._sidebar.set_workspace(ws)
        self._sidebar.show()
        if hasattr(self, '_btn_sidebar'):
            self._btn_sidebar.setChecked(True)
            
        self._command_palette.set_workspace(ws)
        self._search_palette.set_workspace(ws)
        self._tabs.set_workspace(ws)
        self.setWindowTitle(f"amdtr — {ws.name}")
        self._lbl_workspace.setText(str(ws.root))
        self._settings.setValue("last_workspace", str(ws.root))
        
        # Hintergrund-Indexierung starten
        self._index_workspace_background()

    def _index_workspace_background(self) -> None:
        """Indiziert den gesamten Workspace im Hintergrund via QThread."""
        if not self._workspace:
            return
            
        from PyQt6.QtCore import QThread, pyqtSignal

        class IndexWorker(QThread):
            finished = pyqtSignal()
            
            def __init__(self, workspace: Workspace):
                super().__init__()
                self.workspace = workspace
                
            def run(self):
                print(f"[*] Starting background indexing for {self.workspace.name}...")
                for note_path in self.workspace.all_notes():
                    try:
                        content = note_path.read_text(encoding="utf-8")
                        self.workspace.index.add_or_update(note_path, content)
                    except Exception:
                        pass
                self.finished.emit()

        self._index_thread = IndexWorker(self._workspace)
        self._index_thread.finished.connect(lambda: print("[+] Indexing complete."))
        self._index_thread.start()

    # ── Session Persistenz ────────────────────────────────────────────

    def _restore_session(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self._settings.value("splitter_state")
        if splitter_state:
            self._splitter.restoreState(splitter_state)

        last_ws = self._settings.value("last_workspace", "")
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
        """
        closeEvent wird aufgerufen kurz bevor das Fenster geschlossen wird.
        Wir fragen nach ungespeicherten Änderungen und speichern den Zustand.
        Wichtig: event.ignore() bricht das Schließen ab, event.accept() erlaubt es.
        """
        if self._tabs.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Some files have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                self._tabs.save_all()

        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter_state", self._splitter.saveState())
        event.accept()
