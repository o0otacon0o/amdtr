"""
Editor-Preview-Split — kombiniert Editor und Live-Preview in einem QSplitter
"""
from PyQt6.QtWidgets import (
    QSplitter, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from pathlib import Path
from .editor_panel import EditorPanel
from .preview_panel import PreviewPanel
from core.wikilink_resolver import WikilinkResolver
from themes.schema import Theme


class SearchPanel(QFrame):
    """Kompakte Suchleiste für Editor und Preview."""
    search_requested = pyqtSignal(str, bool)  # text, forward
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(lambda t: self.search_requested.emit(t, True))
        self.search_input.returnPressed.connect(lambda: self.search_requested.emit(self.search_input.text(), True))

        self.btn_prev = QPushButton("↑")
        self.btn_prev.setFixedSize(24, 24)
        self.btn_prev.clicked.connect(lambda: self.search_requested.emit(self.search_input.text(), False))

        self.btn_next = QPushButton("↓")
        self.btn_next.setFixedSize(24, 24)
        self.btn_next.clicked.connect(lambda: self.search_requested.emit(self.search_input.text(), True))

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.close_requested.emit)

        layout.addWidget(QLabel("Find:"))
        layout.addWidget(self.search_input)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)
        layout.addStretch()
        layout.addWidget(self.btn_close)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()


class EditorPreviewSplit(QWidget):
    """
    Kombiniert EditorPanel und PreviewPanel mit 150ms Live-Sync.
    
    Layout: [Editor | Preview] (horizontal split)
    
    Features:
    - Editor-Änderungen → Preview Update (150ms debounced)
    - Bidirektionale Scroll-Synchronisation
    - Integrierte Suche (Ctrl+F)
    - Preview kann ein-/ausgeblendet werden
    - Erhält alle EditorPanel Signals weiter
    """
    
    # Signals von EditorPanel weiterleiten
    dirty_state_changed = pyqtSignal(bool)
    content_changed = pyqtSignal(str)  # Neues Signal für Preview-Updates
    wikilink_requested = pyqtSignal(Path)  # Wikilink-Navigation angefordert
    
    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._preview_visible = True
        self._editor_visible = True
        self._scroll_sync_enabled = False
        
        self._setup_ui()
        self._setup_connections()
        self._setup_actions()
        
    def set_theme(self, theme: Theme) -> None:
        """Propagiert das Theme an Editor und Preview."""
        self._editor.set_theme(theme.editor)
        self._preview.set_theme(theme.preview)
        
        # Suchleiste-Farben anpassen
        self._search_panel.setStyleSheet(f"""
            #SearchPanel {{
                background-color: {theme.ui.sidebar_bg};
                border-top: 1px solid {theme.ui.border};
            }}
            QPushButton {{
                background-color: {theme.ui.button_bg};
                color: {theme.ui.button_fg};
                border: 1px solid {theme.ui.border};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.ui.tab_active_bg};
            }}
        """)
        
    def _setup_ui(self) -> None:
        """UI-Layout: Editor | Preview + Search Bar"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Horizontaler Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Editor-Panel (QScintilla)
        self._editor = EditorPanel(self._file_path)
        
        # Preview-Panel (QWebEngineView)
        self._preview = PreviewPanel()
        
        # Zu Splitter hinzufügen
        self._splitter.addWidget(self._editor)
        self._splitter.addWidget(self._preview)
        
        # Standard-Proportionen: 60% Editor, 40% Preview
        self._splitter.setSizes([600, 400])
        self._splitter.setStretchFactor(0, 1)  # Editor strecken
        self._splitter.setStretchFactor(1, 1)  # Preview strecken
        
        main_layout.addWidget(self._splitter, 1) # 1 = Nimmt allen überschüssigen Platz ein

        # Suchleiste
        self._search_panel = SearchPanel(self)
        self._search_panel.hide()
        main_layout.addWidget(self._search_panel, 0) # 0 = Nur so viel Platz wie nötig

    def _setup_actions(self):
        """Tastenkürzel für Suche."""
        self.act_find = QAction("Find", self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.triggered.connect(self._on_toggle_search)
        self.addAction(self.act_find)

    def _setup_connections(self) -> None:
        """Signal-Verbindungen für Live-Sync und Suche"""
        # Editor → Preview: Text-Änderungen
        self._editor.text_changed.connect(self._on_editor_changed)
        
        # Editor → Preview: Scroll-Sync (beim Scrollen im Editor)
        self._editor.scroll_changed.connect(self._on_editor_scroll)
        
        # Editor → Preview: Cursor-Position für Scroll-Sync (beim Tippen/Navigieren)
        self._editor.cursor_position_changed.connect(self._on_cursor_moved)
        
        # Preview → Editor: Scroll-Sync rückwärts
        self._preview.scroll_to_line.connect(self._on_preview_scroll)
        
        # EditorPanel Signals weiterleiten
        self._editor.dirty_state_changed.connect(self.dirty_state_changed.emit)
        self._editor.wikilink_requested.connect(self.wikilink_requested.emit)

        # Suche
        self._search_panel.search_requested.connect(self._on_search_requested)
        self._search_panel.close_requested.connect(self._search_panel.hide)
        
        print(f"[DEBUG] EditorPreviewSplit: Setup connections completed")
        
        # Initial preview mit aktuellem Editor-Inhalt laden
        self._update_preview()

    def _on_toggle_search(self):
        """Blendet die Suchleiste ein/aus."""
        if self._search_panel.isVisible():
            if self._search_panel.search_input.hasFocus():
                self._search_panel.hide()
                # Preview-Highlights löschen (leere Suche triggern)
                self._preview.find_text("")
                self._editor.setFocus()
            else:
                self._search_panel.focus_search()
        else:
            self._search_panel.show()
            self._search_panel.focus_search()

    def _on_search_requested(self, text: str, forward: bool):
        """Führt die Suche in Editor und Preview aus."""
        # 1. Editor-Suche
        self._editor.find_text(text, forward)
        
        # 2. Preview-Suche
        self._preview.find_text(text, forward)

    def _on_editor_changed(self) -> None:
        """Editor-Text hat sich geändert → Preview aktualisieren"""
        print(f"[DEBUG] EditorPreviewSplit._on_editor_changed called")
        self._update_preview()
        self.content_changed.emit(self._editor.get_text())
        
    def _on_editor_scroll(self, first_line: int) -> None:
        """Editor wurde gescrollt → Preview mitziehen"""
        if self._preview_visible and self._scroll_sync_enabled:
            # 1-basiert für Preview. Wir nutzen die erste sichtbare Zeile.
            self._preview.scroll_to_line_number(first_line + 1)

    def _on_cursor_moved(self, line: int, index: int) -> None:
        """Cursor im Editor bewegt → Preview scrollen"""
        # Nur wenn der Cursor wirklich bewegt wurde, soll die Vorschau folgen.
        if self._preview_visible and self._scroll_sync_enabled:
            self._preview.scroll_to_line_number(line + 1)
            
    def _on_preview_scroll(self, line: int) -> None:
        """Preview gescrollt → Editor nur scrollen (nicht Cursor bewegen)"""
        if line > 0 and self._scroll_sync_enabled:
            # WICHTIG: Nutze set_first_visible_line statt set_cursor_position,
            # damit der Editor nicht "springt" und den Cursor verliert.
            self._editor.set_first_visible_line(line - 1)
            
    def _update_preview(self) -> None:
        """Aktuellen Editor-Inhalt an Preview senden"""
        if self._preview_visible:
            markdown_text = self._editor.get_text()
            line, _ = self._editor.get_cursor_position()
            self._preview.update_markdown(markdown_text, line + 1)
    
    # ── Public API (EditorPanel-kompatibel) ──────────────────────────
    
    def path(self) -> Path:
        """Dateipfad des geöffneten Dokuments"""
        return self._editor.path()
        
    def is_dirty(self) -> bool:
        """Sind ungespeicherte Änderungen vorhanden?"""
        return self._editor.is_dirty()
        
    def save(self) -> None:
        """Datei speichern"""
        self._editor.save()
        
    def toPlainText(self) -> str:
        """Aktueller Editor-Inhalt als String"""
        return self._editor.get_text()
        
    def setText(self, text: str) -> None:
        """Editor-Inhalt setzen"""
        self._editor.set_text(text)
        
    # ── Visibility Control ──────────────────────────────────────────────
    
    def set_view_mode(self, mode: str) -> None:
        """
        Setzt den Ansichtsmodus: 'editor', 'split', oder 'preview'.
        """
        if mode == 'editor':
            self._editor_visible = True
            self._preview_visible = False
        elif mode == 'preview':
            self._editor_visible = False
            self._preview_visible = True
        else: # split
            self._editor_visible = True
            self._preview_visible = True
            
        self._editor.setVisible(self._editor_visible)
        self._preview.setVisible(self._preview_visible)
        
        if self._preview_visible:
            self._update_preview()

    def get_view_mode(self) -> str:
        """Gibt den aktuellen Ansichtsmodus zurück."""
        if self._editor_visible and self._preview_visible:
            return 'split'
        if self._editor_visible:
            return 'editor'
        return 'preview'

    def toggle_preview(self) -> None:
        """Klassischer Toggle (wird von MainWindow genutzt)."""
        if self._preview_visible and not self._editor_visible:
            return # Verhindere dass alles unsichtbar wird
        self.set_view_mode('split' if not self._preview_visible else 'editor')
            
    def is_preview_visible(self) -> bool:
        """Ist Preview aktuell sichtbar?"""
        return self._preview_visible

    def is_editor_visible(self) -> bool:
        """Ist Editor aktuell sichtbar?"""
        return self._editor_visible

    def set_scroll_sync_enabled(self, enabled: bool) -> None:
        """Aktiviert/Deaktiviert Scroll-Sync."""
        self._scroll_sync_enabled = enabled

    def is_scroll_sync_enabled(self) -> bool:
        """Gibt zurück ob Scroll-Sync aktiv ist."""
        return self._scroll_sync_enabled
    
    # ── Wikilink-System ───────────────────────────────────────────────
    
    def set_wikilink_resolver(self, resolver: WikilinkResolver | None) -> None:
        """Setzt den Wikilink-Resolver für Link-Navigation."""
        self._editor.set_wikilink_resolver(resolver)
    
    # ── Editor-Zugriff für erweiterte Features ─────────────────────────
    
    def editor(self) -> EditorPanel:
        """Direkter Zugriff auf EditorPanel für erweiterte Features"""
        return self._editor
        
    def preview(self) -> PreviewPanel:
        """Direkter Zugriff auf PreviewPanel für erweiterte Features"""  
        return self._preview