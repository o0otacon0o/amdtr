"""
EditorPanel — QScintilla-based Markdown editor.

Replaces the previous EditorPlaceholder (QTextEdit) with a
full-featured editor providing syntax highlighting, line numbers,
code folding, and advanced features.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase, QCursor, QColor
from PyQt6.Qsci import QsciScintilla, QsciCommand
from core.document_model import DocumentModel
from core.file_manager import FileManager
from core.wikilink_resolver import WikilinkResolver
from editor.md_mermaid_lexer import MdMermaidLexer
from themes.schema import EditorTheme


class VimController:
    """
    Experimental Vim state machine for QScintilla.
    Since setViMode is not available in all PyQt6-QScintilla builds,
    we implement a basic version manually.
    """
    MODE_NORMAL = "NORMAL"
    MODE_INSERT = "INSERT"
    
    def __init__(self, editor: QsciScintilla):
        self.editor = editor
        self.mode = self.MODE_NORMAL
        self._pending_op = ""
        
    def get_status(self) -> str:
        """Returns the status string for the UI."""
        status = self.mode
        if self._pending_op:
            status += f" {self._pending_op}"
        return status

    def handle_key(self, event) -> bool:
        """
        Handles key events. 
        Returns True if the event was consumed.
        """
        key = event.key()
        text = event.text()
        
        if self.mode == self.MODE_INSERT:
            if key == Qt.Key.Key_Escape:
                self.mode = self.MODE_NORMAL
                self._pending_op = ""
                self.editor.setCaretWidth(10) # Simulates block cursor
                return True
            return False # Let editor handle typing
            
        # --- NORMAL MODE ---
        if key == Qt.Key.Key_I:
            self.mode = self.MODE_INSERT
            self._pending_op = ""
            self.editor.setCaretWidth(1) # Normal line cursor
            return True
            
        # Basic Navigation
        nav_map = {
            Qt.Key.Key_H: QsciScintilla.SCI_CHARLEFT,
            Qt.Key.Key_L: QsciScintilla.SCI_CHARRIGHT,
            Qt.Key.Key_J: QsciScintilla.SCI_LINEDOWN,
            Qt.Key.Key_K: QsciScintilla.SCI_LINEUP,
            Qt.Key.Key_0: QsciScintilla.SCI_VCHOME,
            Qt.Key.Key_X: QsciScintilla.SCI_CLEAR,
            Qt.Key.Key_U: QsciScintilla.SCI_UNDO,
        }
        
        if key in nav_map:
            self.editor.SendScintilla(nav_map[key])
            self._pending_op = ""
            return True
            
        if text == "$":
            self.editor.SendScintilla(QsciScintilla.SCI_LINEEND)
            self._pending_op = ""
            return True
            
        # Double-key commands (e.g., dd)
        if text == "d":
            if self._pending_op == "d":
                self.editor.SendScintilla(QsciScintilla.SCI_LINEDELETE)
                self._pending_op = ""
            else:
                self._pending_op = "d"
            return True
        
        self._pending_op = ""
        return True # Consume all other keys in Normal mode


class EditorPanel(QWidget):
    """
    Editor panel with QScintilla for advanced text editing.
    
    Features:
    - Syntax highlighting for Markdown + Mermaid
    - Line numbers and code folding
    - Auto-completion and auto-pairing
    - Undo/Redo with QUndoStack integration
    """
    
    # Signals for parent widget (TabWidget)
    text_changed = pyqtSignal()
    dirty_state_changed = pyqtSignal(bool)
    cursor_position_changed = pyqtSignal(int, int)  # line, column
    scroll_changed = pyqtSignal(int)               # First visible line
    wikilink_requested = pyqtSignal(Path)  # User wants to open a wikilink
    vim_status_changed = pyqtSignal(str)   # Mode + pending keys
    
    def __init__(self, file_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        # Document Model
        self._document = DocumentModel(file_path, self)
        self._file_manager = FileManager()
        
        # Wikilink resolver (set from outside)
        self._wikilink_resolver: WikilinkResolver | None = None
        
        self._vim_mode = False
        
        self._setup_ui()
        self._setup_editor()
        
        # Initialize Vim Controller after setup_ui so _editor exists
        self._vim_controller = VimController(self._editor)
        self._editor.installEventFilter(self)
        
        self._load_file()
        self._wire_signals()

    def eventFilter(self, obj, event) -> bool:
        if obj == self._editor and event.type() == event.Type.KeyPress:
            if self._vim_mode:
                consumed = self._vim_controller.handle_key(event)
                if consumed:
                    self.vim_status_changed.emit(self._vim_controller.get_status())
                return consumed
        return super().eventFilter(obj, event)

    def set_vim_mode(self, enabled: bool) -> None:
        """Enables or disables Vim (Vi) modal editing."""
        self._vim_mode = enabled
        
        # Adjust caret style for better Vim feel
        if enabled:
            self._editor.setCaretWidth(10) # Simulates block cursor
            self._vim_controller.mode = VimController.MODE_NORMAL
            self.vim_status_changed.emit(self._vim_controller.get_status())
        else:
            self._editor.setCaretWidth(1) # Normal line cursor
            self.vim_status_changed.emit("")
        
        self._editor.setFocus()
        
    def _setup_ui(self) -> None:
        """Create UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # QScintilla Editor
        self._editor = QsciScintilla()
        layout.addWidget(self._editor)
        
    def _setup_editor(self) -> None:
        """Configure QScintilla."""
        # Lexer for syntax highlighting
        self._lexer = MdMermaidLexer(self._editor)
        self._editor.setLexer(self._lexer)
        
        # Basic configuration
        self._editor.setUtf8(True)
        self._editor.setIndentationsUseTabs(False)
        self._editor.setIndentationWidth(4)
        self._editor.setAutoIndent(True)
        
        # Line numbers
        self._editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self._editor.setMarginLineNumbers(0, True)
        self._editor.setMarginSensitivity(0, False)
        
        # Disable other margins (remove symbol margin 1)
        self._editor.setMarginWidth(1, 0)
        
        # Code folding
        self._editor.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        
        # Cursor and selection
        self._editor.setCaretLineVisible(True)
        
        # Brace matching
        self._editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        
        # Set font
        font = self._get_editor_font()
        self._editor.setFont(font)
        self._lexer.setFont(font)
        
        # Whitespace and EOL
        self._editor.setEolMode(QsciScintilla.EolMode.EolUnix)
        self._editor.setEolVisibility(False)
        self._editor.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsInvisible)
        
        # Tab behavior
        self._editor.setTabWidth(4)
        
        # Word wrap
        self._editor.setWrapMode(QsciScintilla.WrapMode.WrapWord)
        self._editor.setWrapVisualFlags(QsciScintilla.WrapVisualFlag.WrapFlagByText)
        
        # Mouse events for wikilink navigation
        self._editor.mousePressEvent = self._on_mouse_press
        
    def set_theme(self, theme: EditorTheme) -> None:
        """Applies an editor theme."""
        # Colors for editor widget
        bg_color = QColor(theme.background)
        fg_color = QColor(theme.foreground)
        
        self._editor.setPaper(bg_color)
        self._editor.setColor(fg_color)
        
        # IMPORTANT: Set default style of the lexer directly for the background
        if self._lexer:
            # setDefaultPaper/Color exist in QsciLexer
            self._lexer.setDefaultPaper(bg_color)
            self._lexer.setDefaultColor(fg_color)
            self._lexer.set_theme(theme)
        
        # Line numbers
        self._editor.setMarginsBackgroundColor(QColor(theme.line_number_bg))
        self._editor.setMarginsForegroundColor(QColor(theme.line_number_fg))
        
        # Visually remove folding bars (match background to editor)
        self._editor.setFoldMarginColors(bg_color, bg_color)
        
        # Caret and selection
        self._editor.setCaretForegroundColor(fg_color)
        self._editor.setCaretLineBackgroundColor(QColor(theme.current_line))
        self._editor.setSelectionBackgroundColor(QColor(theme.selection_bg))
        self._editor.setSelectionForegroundColor(QColor(theme.selection_fg))
        
        # Refresh
        self._update_line_number_width()
        self._editor.update()
        
    def _get_editor_font(self) -> QFont:
        """Determines the best available monospace font."""
        preferred_fonts = [
            "Cascadia Code", "Cascadia Mono", "JetBrains Mono",
            "Fira Code", "Source Code Pro", "Consolas", "Monaco", 
            "Courier New"
        ]
        
        available_families = QFontDatabase.families()
        
        for font_name in preferred_fonts:
            if font_name in available_families:
                font = QFont(font_name)
                font.setPointSize(11)
                font.setFixedPitch(True)
                return font
        
        # Fallback: system monospace
        font = QFont()
        font.setFixedPitch(True)
        font.setPointSize(11)
        font.setFamily("monospace")
        return font
        
    def _wire_signals(self) -> None:
        """Connect signals to slots."""
        # Text changes
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.textChanged.connect(self._update_line_number_width)
        
        # Cursor position
        self._editor.cursorPositionChanged.connect(self._on_cursor_changed)
        
        # Document model signals
        self._document.dirty_state_changed.connect(self.dirty_state_changed.emit)
        
        # Scroll sync (editor -> preview)
        self._editor.verticalScrollBar().valueChanged.connect(
            lambda: self.scroll_changed.emit(self._editor.firstVisibleLine())
        )

    def set_first_visible_line(self, line: int) -> None:
        """Scrolls the editor so that the specified line is visible at the top."""
        self._editor.setFirstVisibleLine(line)

    def _update_line_number_width(self) -> None:
        """Adjusts the width of the line number margin to the number of lines."""
        lines = self._editor.lines()
        width = len(str(lines))
        # Use '9' instead of '0' for width calculation (often the widest character)
        format_str = "9" * max(2, width) + " "
        self._editor.setMarginWidth(0, format_str)
        
    def _load_file(self) -> None:
        """Load file content."""
        success = self._document.load_from_disk()
        if success:
            # Set text in editor (without triggering signals)
            self._editor.blockSignals(True)
            self._editor.setText(self._document.text)
            self._editor.blockSignals(False)
            
            # Restore cursor position
            line, col = self._document.get_cursor_position()
            self._editor.setCursorPosition(line, col)
        else:
            # New or unreadable file
            self._editor.setText("")
    
    # ── Public Interface ──────────────────────────────────────────────
    
    def path(self) -> Path:
        """File path of the open document."""
        return self._document.path
        
    def is_dirty(self) -> bool:
        """True if there are unsaved changes."""
        return self._document.dirty
        
    def save(self) -> bool:
        """
        Saves the document.
        Returns True if successful.
        """
        # Transfer current text to document model
        current_text = self._editor.text()
        if self._document.text != current_text:
            self._document.text = current_text
            
        # Save cursor position
        line, col = self._editor.getCursorPosition()
        self._document.set_cursor_position(line, col)
        
        # Save to disk
        success = self._document.save_to_disk()
        
        if not success:
            QMessageBox.critical(
                self, "Save Error",
                f"Could not save {self._document.path.name}"
            )
            
        return success
        
    def get_selected_text(self) -> str:
        """Returns the currently selected text."""
        return self._editor.selectedText()
        
    def insert_text(self, text: str) -> None:
        """Inserts text at the cursor position."""
        self._editor.insert(text)
        
    def get_cursor_position(self) -> tuple[int, int]:
        """Returns current cursor position (line, column)."""
        return self._editor.getCursorPosition()
        
    def set_cursor_position(self, line: int, column: int) -> None:
        """Sets cursor position."""
        self._editor.setCursorPosition(line, column)
        
    def get_line_count(self) -> int:
        """Returns the number of lines."""
        return self._editor.lines()
        
    def get_text(self) -> str:
        """Returns the full editor text."""
        return self._editor.text()
        
    def set_text(self, text: str) -> None:
        """Sets the full editor text."""
        self._editor.setText(text)
    
    def set_wikilink_resolver(self, resolver: WikilinkResolver | None) -> None:
        """Sets the wikilink resolver for link navigation."""
        self._wikilink_resolver = resolver
        self._document.set_wikilink_resolver(resolver)
    
    def get_document_model(self) -> DocumentModel:
        """Returns the document model (for integration with other components)."""
        return self._document
        
    def find_text(self, text: str, forward: bool = True) -> bool:
        """
        Searches for text in the editor.
        Returns True if a match was found.
        """
        if not text:
            # Clear selection if search is empty
            line, col = self._editor.getCursorPosition()
            self._editor.setSelection(line, col, line, col)
            return False

        # Configure search
        re = False      # Regular expression
        cs = False      # Case sensitive
        wo = False      # Whole word
        wrap = True     # Wrap around
        
        if forward:
            # findNext() continues where findFirst() left off
            return self._editor.findFirst(text, re, cs, wo, wrap, forward)
        else:
            # Backward search
            return self._editor.findFirst(text, re, cs, wo, wrap, forward)

    # ── Slots ─────────────────────────────────────────────────────────
    
    def _on_text_changed(self) -> None:
        """Text has changed."""
        # Update document model
        current_text = self._editor.text()
        if self._document.text != current_text:
            self._document.text = current_text
        
        # Forward signal
        self.text_changed.emit()
        
    def _on_cursor_changed(self, line: int, index: int) -> None:
        """Cursor position has changed."""
        # Save position in document model
        self._document.set_cursor_position(line, index)

        # Forward signal
        self.cursor_position_changed.emit(line, index)

    def _on_mouse_press(self, event) -> None:
        """
        Mouse press event handler for Ctrl+Click wikilink navigation.

        Overrides QScintilla's mousePressEvent to intercept wikilink clicks.
        """
        # Ctrl+Click for wikilink navigation
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier and
            event.button() == Qt.MouseButton.LeftButton):

            # Determine position under mouse
            pos = event.position().toPoint()
            char_pos = self._editor.positionFromPoint(pos.x(), pos.y())

            if char_pos >= 0:
                # Check if there is a wikilink at this position
                resolved_path = self._document.resolve_wikilink_at_position(char_pos)
                if resolved_path:
                    # Wikilink found - request navigation
                    self.wikilink_requested.emit(resolved_path)
                    return  # Don't forward event

        # Standard behavior for all other clicks
        QsciScintilla.mousePressEvent(self._editor, event)
