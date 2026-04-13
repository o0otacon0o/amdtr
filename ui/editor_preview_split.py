"""
Editor-Preview-Split — combines editor and live preview in a QSplitter.
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
    """Compact search bar for editor and preview."""
    search_requested = pyqtSignal(str, bool)  # text, forward
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self._setup_ui()

    def _setup_ui(self):
        """Initializes the search panel UI."""
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
        """Focuses the search input field and selects all text."""
        self.search_input.setFocus()
        self.search_input.selectAll()


class EditorPreviewSplit(QWidget):
    """
    Combines EditorPanel and PreviewPanel with 150ms live-sync.
    
    Layout: [Editor | Preview] (horizontal split)
    
    Features:
    - Editor changes → Preview update (150ms debounced)
    - Bidirectional scroll synchronization
    - Integrated search (Ctrl+F)
    - Preview can be toggled on/off
    - Forwards all EditorPanel signals
    """
    
    # Forward signals from EditorPanel
    dirty_state_changed = pyqtSignal(bool)
    content_changed = pyqtSignal(str)  # New signal for preview updates
    wikilink_requested = pyqtSignal(Path)  # Wikilink navigation requested
    
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
        """Propagates the theme to editor and preview."""
        self._editor.set_theme(theme.editor)
        self._preview.set_theme(theme.preview)
        
        # Adjust search bar colors
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

        # Horizontal splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Editor-Panel (QScintilla)
        self._editor = EditorPanel(self._file_path)
        
        # Preview-Panel (QWebEngineView)
        self._preview = PreviewPanel()
        self._preview.set_base_path(self._file_path.parent)
        
        # Add to splitter
        self._splitter.addWidget(self._editor)
        self._splitter.addWidget(self._preview)
        
        # Default proportions: 60% editor, 40% preview
        self._splitter.setSizes([600, 400])
        self._splitter.setStretchFactor(0, 1)  # Stretch editor
        self._splitter.setStretchFactor(1, 1)  # Stretch preview
        
        main_layout.addWidget(self._splitter, 1) # 1 = Takes all excess space

        # Search bar
        self._search_panel = SearchPanel(self)
        self._search_panel.hide()
        main_layout.addWidget(self._search_panel, 0) # 0 = Only as much space as needed

    def _setup_actions(self):
        """Keyboard shortcuts for search."""
        self.act_find = QAction("Find", self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.triggered.connect(self._on_toggle_search)
        self.addAction(self.act_find)

    def _setup_connections(self) -> None:
        """Signal connections for live-sync and search."""
        # Editor → Preview: text changes
        self._editor.text_changed.connect(self._on_editor_changed)
        
        # Editor → Preview: scroll-sync (when scrolling in editor)
        self._editor.scroll_changed.connect(self._on_editor_scroll)
        
        # Editor → Preview: cursor position for scroll-sync (when typing/navigating)
        self._editor.cursor_position_changed.connect(self._on_cursor_moved)
        
        # Preview → Editor: backwards scroll-sync
        self._preview.scroll_to_line.connect(self._on_preview_scroll)
        
        # Forward EditorPanel signals
        self._editor.dirty_state_changed.connect(self.dirty_state_changed.emit)
        self._editor.wikilink_requested.connect(self.wikilink_requested.emit)

        # Search
        self._search_panel.search_requested.connect(self._on_search_requested)
        self._search_panel.close_requested.connect(self._search_panel.hide)
        
        print(f"[DEBUG] EditorPreviewSplit: Setup connections completed")
        
        # Load initial preview with current editor content
        self._update_preview()

    def _on_toggle_search(self):
        """Toggles the search bar visibility."""
        if self._search_panel.isVisible():
            if self._search_panel.search_input.hasFocus():
                self._search_panel.hide()
                # Clear preview highlights (trigger empty search)
                self._preview.find_text("")
                self._editor.setFocus()
            else:
                self._search_panel.focus_search()
        else:
            self._search_panel.show()
            self._search_panel.focus_search()

    def _on_search_requested(self, text: str, forward: bool):
        """Executes search in both editor and preview."""
        # 1. Editor search
        self._editor.find_text(text, forward)
        
        # 2. Preview search
        self._preview.find_text(text, forward)

    def _on_editor_changed(self) -> None:
        """Editor text has changed → update preview."""
        print(f"[DEBUG] EditorPreviewSplit._on_editor_changed called")
        self._update_preview()
        self.content_changed.emit(self._editor.get_text())
        
    def _on_editor_scroll(self, first_line: int) -> None:
        """Editor was scrolled → sync preview."""
        if self._preview_visible and self._scroll_sync_enabled:
            # 1-based for preview. We use the first visible line.
            self._preview.scroll_to_line_number(first_line + 1)

    def _on_cursor_moved(self, line: int, index: int) -> None:
        """Cursor moved in editor → scroll preview."""
        # Only if the cursor was actually moved should the preview follow.
        if self._preview_visible and self._scroll_sync_enabled:
            self._preview.scroll_to_line_number(line + 1)
            
    def _on_preview_scroll(self, line: int) -> None:
        """Preview scrolled → scroll editor only (do not move cursor)."""
        if line > 0 and self._scroll_sync_enabled:
            # IMPORTANT: Use set_first_visible_line instead of set_cursor_position,
            # so the editor doesn't "jump" and lose the cursor.
            self._editor.set_first_visible_line(line - 1)
            
    def _update_preview(self) -> None:
        """Send current editor content to preview."""
        if self._preview_visible:
            markdown_text = self._editor.get_text()
            line, _ = self._editor.get_cursor_position()
            self._preview.update_markdown(markdown_text, line + 1)
    
    # ── Public API (EditorPanel-compatible) ──────────────────────────
    
    def path(self) -> Path:
        """File path of the open document."""
        return self._editor.path()
        
    def is_dirty(self) -> bool:
        """Are there unsaved changes?"""
        return self._editor.is_dirty()
        
    def save(self) -> None:
        """Save file."""
        self._editor.save()
        
    def toPlainText(self) -> str:
        """Current editor content as string."""
        return self._editor.get_text()
        
    def setText(self, text: str) -> None:
        """Set editor content."""
        self._editor.set_text(text)
        
    # ── Visibility Control ──────────────────────────────────────────────
    
    def set_view_mode(self, mode: str) -> None:
        """
        Sets the view mode: 'editor', 'split', or 'preview'.
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
        """Returns the current view mode."""
        if self._editor_visible and self._preview_visible:
            return 'split'
        if self._editor_visible:
            return 'editor'
        return 'preview'

    def toggle_preview(self) -> None:
        """Classic toggle (used by MainWindow)."""
        if self._preview_visible and not self._editor_visible:
            return # Prevent everything from becoming invisible
        self.set_view_mode('split' if not self._preview_visible else 'editor')
            
    def is_preview_visible(self) -> bool:
        """Is the preview currently visible?"""
        return self._preview_visible

    def is_editor_visible(self) -> bool:
        """Is the editor currently visible?"""
        return self._editor_visible

    def set_scroll_sync_enabled(self, enabled: bool) -> None:
        """Enables/disables scroll-sync."""
        self._scroll_sync_enabled = enabled

    def is_scroll_sync_enabled(self) -> bool:
        """Returns whether scroll-sync is active."""
        return self._scroll_sync_enabled
    
    # ── Wikilink System ───────────────────────────────────────────────
    
    def set_wikilink_resolver(self, resolver: WikilinkResolver | None) -> None:
        """Sets the wikilink resolver for link navigation."""
        self._editor.set_wikilink_resolver(resolver)
    
    def set_vim_mode(self, enabled: bool) -> None:
        """Propagates Vim mode to the editor."""
        self._editor.set_vim_mode(enabled)
    
    # ── Editor Access for advanced features ───────────────────────────
    
    def editor(self) -> EditorPanel:
        """Direct access to EditorPanel for advanced features."""
        return self._editor
        
    def preview(self) -> PreviewPanel:
        """Direct access to PreviewPanel for advanced features."""  
        return self._preview
