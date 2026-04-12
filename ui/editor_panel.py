"""
EditorPanel — QScintilla-basierter Markdown-Editor.

Ersetzt das bisherige EditorPlaceholder (QTextEdit) durch einen
vollwertigen Editor mit Syntax-Highlighting, Zeilennummern,
Code-Folding und erweiterten Features.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase, QCursor, QColor
from PyQt6.Qsci import QsciScintilla
from core.document_model import DocumentModel
from core.file_manager import FileManager
from core.wikilink_resolver import WikilinkResolver
from editor.md_mermaid_lexer import MdMermaidLexer
from themes.schema import EditorTheme


class EditorPanel(QWidget):
    """
    Editor-Panel mit QScintilla für erweiterte Text-Bearbeitung.
    
    Features:
    - Syntax-Highlighting für Markdown + Mermaid
    - Zeilennummern und Code-Folding
    - Auto-Completion und Auto-Pairing
    - Undo/Redo mit QUndoStack Integration
    """
    
    # Signals für Parent-Widget (TabWidget)
    text_changed = pyqtSignal()
    dirty_state_changed = pyqtSignal(bool)
    cursor_position_changed = pyqtSignal(int, int)  # line, column
    scroll_changed = pyqtSignal(int)               # Erste sichtbare Zeile
    wikilink_requested = pyqtSignal(Path)  # User möchte Wikilink öffnen
    
    def __init__(self, file_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        # Document Model
        self._document = DocumentModel(file_path, self)
        self._file_manager = FileManager()
        
        # Wikilink-Resolver (wird von außen gesetzt)
        self._wikilink_resolver: WikilinkResolver | None = None
        
        self._setup_ui()
        self._setup_editor()
        self._load_file()
        self._wire_signals()
        
    def _setup_ui(self) -> None:
        """UI-Layout erstellen."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # QScintilla Editor
        self._editor = QsciScintilla()
        layout.addWidget(self._editor)
        
    def _setup_editor(self) -> None:
        """QScintilla konfigurieren."""
        # Lexer für Syntax-Highlighting
        self._lexer = MdMermaidLexer(self._editor)
        self._editor.setLexer(self._lexer)
        
        # Basis-Konfiguration
        self._editor.setUtf8(True)
        self._editor.setIndentationsUseTabs(False)
        self._editor.setIndentationWidth(4)
        self._editor.setAutoIndent(True)
        
        # Zeilennummern
        self._editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self._editor.setMarginLineNumbers(0, True)
        self._editor.setMarginSensitivity(0, False)
        
        # Andere Margins deaktivieren (Symbol-Margin 1 entfernen)
        self._editor.setMarginWidth(1, 0)
        
        # Code-Folding
        self._editor.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        
        # Cursor und Selection
        self._editor.setCaretLineVisible(True)
        
        # Brace-Matching
        self._editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        
        # Schrift setzen
        font = self._get_editor_font()
        self._editor.setFont(font)
        self._lexer.setFont(font)
        
        # Whitespace und EOL
        self._editor.setEolMode(QsciScintilla.EolMode.EolUnix)
        self._editor.setEolVisibility(False)
        self._editor.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsInvisible)
        
        # Tab-Verhalten
        self._editor.setTabWidth(4)
        
        # Zeilenumbruch (Word Wrap)
        self._editor.setWrapMode(QsciScintilla.WrapMode.WrapWord)
        self._editor.setWrapVisualFlags(QsciScintilla.WrapVisualFlag.WrapFlagByText)
        
        # Mouse-Events für Wikilink-Navigation
        self._editor.mousePressEvent = self._on_mouse_press
        
    def set_theme(self, theme: EditorTheme) -> None:
        """Wendet ein Editor-Theme an."""
        # Farben für Editor-Widget
        bg_color = QColor(theme.background)
        fg_color = QColor(theme.foreground)
        
        self._editor.setPaper(bg_color)
        self._editor.setColor(fg_color)
        
        # WICHTIG: Default-Style des Lexers auch direkt setzen für den Hintergrund
        if self._lexer:
            # setDefaultPaper/Color existieren in QsciLexer
            self._lexer.setDefaultPaper(bg_color)
            self._lexer.setDefaultColor(fg_color)
            self._lexer.set_theme(theme)
        
        # Zeilennummern
        self._editor.setMarginsBackgroundColor(QColor(theme.line_number_bg))
        self._editor.setMarginsForegroundColor(QColor(theme.line_number_fg))
        
        # Folding-Balken visuell entfernen (Hintergrund an Editor anpassen)
        self._editor.setFoldMarginColors(bg_color, bg_color)
        
        # Caret und Selection
        self._editor.setCaretForegroundColor(fg_color)
        self._editor.setCaretLineBackgroundColor(QColor(theme.current_line))
        self._editor.setSelectionBackgroundColor(QColor(theme.selection_bg))
        self._editor.setSelectionForegroundColor(QColor(theme.selection_fg))
        
        # Refresh
        self._update_line_number_width()
        self._editor.update()
        
    def _get_editor_font(self) -> QFont:
        """Bestimmt die beste verfügbare Monospace-Schrift."""
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
        
        # Fallback: System-Monospace
        font = QFont()
        font.setFixedPitch(True)
        font.setPointSize(11)
        font.setFamily("monospace")
        return font
        
    def _wire_signals(self) -> None:
        """Signals mit Slots verbinden."""
        # Text-Änderungen
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.textChanged.connect(self._update_line_number_width)
        
        # Cursor-Position
        self._editor.cursorPositionChanged.connect(self._on_cursor_changed)
        
        # Document Model Signals
        self._document.dirty_state_changed.connect(self.dirty_state_changed.emit)
        
        # Scroll-Sync (Editor -> Preview)
        self._editor.verticalScrollBar().valueChanged.connect(
            lambda: self.scroll_changed.emit(self._editor.firstVisibleLine())
        )

    def set_first_visible_line(self, line: int) -> None:
        """Scrollt den Editor so, dass die angegebene Zeile oben sichtbar ist."""
        self._editor.setFirstVisibleLine(line)

    def _update_line_number_width(self) -> None:
        """Passt die Breite des Zeilennummern-Margins an die Anzahl der Zeilen an."""
        lines = self._editor.lines()
        width = len(str(lines))
        # Nutze '9' statt '0' für die Breitenberechnung (oft breitestes Zeichen)
        format_str = "9" * max(2, width) + " "
        self._editor.setMarginWidth(0, format_str)
        
    def _load_file(self) -> None:
        """Datei-Inhalt laden."""
        success = self._document.load_from_disk()
        if success:
            # Text in Editor setzen (ohne Signals zu triggern)
            self._editor.blockSignals(True)
            self._editor.setText(self._document.text)
            self._editor.blockSignals(False)
            
            # Cursor-Position wiederherstellen
            line, col = self._document.get_cursor_position()
            self._editor.setCursorPosition(line, col)
        else:
            # Neue/unlesbare Datei
            self._editor.setText("")
    
    # ── Public Interface ──────────────────────────────────────────────
    
    def path(self) -> Path:
        """Dateipfad des geöffneten Dokuments."""
        return self._document.path
        
    def is_dirty(self) -> bool:
        """True wenn ungespeicherte Änderungen existieren."""
        return self._document.dirty
        
    def save(self) -> bool:
        """
        Speichert das Dokument.
        Gibt True zurück wenn erfolgreich.
        """
        # Aktuellen Text ins Document Model übertragen
        current_text = self._editor.text()
        if self._document.text != current_text:
            self._document.text = current_text
            
        # Cursor-Position speichern
        line, col = self._editor.getCursorPosition()
        self._document.set_cursor_position(line, col)
        
        # Auf Disk speichern
        success = self._document.save_to_disk()
        
        if not success:
            QMessageBox.critical(
                self, "Save Error",
                f"Could not save {self._document.path.name}"
            )
            
        return success
        
    def get_selected_text(self) -> str:
        """Gibt den aktuell selektierten Text zurück."""
        return self._editor.selectedText()
        
    def insert_text(self, text: str) -> None:
        """Fügt Text an der Cursor-Position ein."""
        self._editor.insert(text)
        
    def get_cursor_position(self) -> tuple[int, int]:
        """Gibt aktuelle Cursor-Position zurück (line, column)."""
        return self._editor.getCursorPosition()
        
    def set_cursor_position(self, line: int, column: int) -> None:
        """Setzt Cursor-Position."""
        self._editor.setCursorPosition(line, column)
        
    def get_line_count(self) -> int:
        """Gibt Anzahl der Zeilen zurück."""
        return self._editor.lines()
        
    def get_text(self) -> str:
        """Gibt kompletten Editor-Text zurück."""
        return self._editor.text()
        
    def set_text(self, text: str) -> None:
        """Setzt kompletten Editor-Text."""
        self._editor.setText(text)
    
    def set_wikilink_resolver(self, resolver: WikilinkResolver | None) -> None:
        """Setzt den Wikilink-Resolver für Link-Navigation."""
        self._wikilink_resolver = resolver
        self._document.set_wikilink_resolver(resolver)
    
    def get_document_model(self) -> DocumentModel:
        """Gibt das DocumentModel zurück (für Integration mit anderen Komponenten)."""
        return self._document
        
    def find_text(self, text: str, forward: bool = True) -> bool:
        """
        Sucht nach Text im Editor.
        Gibt True zurück wenn ein Treffer gefunden wurde.
        """
        if not text:
            # Selektion aufheben wenn Suche leer
            line, col = self._editor.getCursorPosition()
            self._editor.setSelection(line, col, line, col)
            return False

        # Suche konfigurieren
        re = False      # Regular Expression
        cs = False      # Case Sensitive
        wo = False      # Whole Word
        wrap = True     # Wrap around
        
        if forward:
            # findNext() setzt dort fort wo findFirst() aufgehört hat
            return self._editor.findFirst(text, re, cs, wo, wrap, forward)
        else:
            # Rückwärtssuche
            return self._editor.findFirst(text, re, cs, wo, wrap, forward)

    # ── Slots ─────────────────────────────────────────────────────────
    
    def _on_text_changed(self) -> None:
        """Text wurde geändert."""
        # Document Model aktualisieren
        current_text = self._editor.text()
        if self._document.text != current_text:
            self._document.text = current_text
        
        # Signal weiterleiten
        self.text_changed.emit()
        
    def _on_cursor_changed(self, line: int, index: int) -> None:
        """Cursor-Position geändert."""
        # Position im Document Model speichern
        self._document.set_cursor_position(line, index)

        # Signal weiterleiten
        self.cursor_position_changed.emit(line, index)

    def _on_mouse_press(self, event) -> None:
        """
        Mouse-Press-Event-Handler für Ctrl+Click Wikilink-Navigation.

        Überschreibt QScintilla's mousePressEvent um Wikilink-Clicks abzufangen.
        """
        # Ctrl+Click für Wikilink-Navigation
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier and
            event.button() == Qt.MouseButton.LeftButton):

            # Position unter Maus bestimmen
            pos = event.position().toPoint()
            char_pos = self._editor.positionFromPoint(pos.x(), pos.y())

            if char_pos >= 0:
                # Prüfe ob an dieser Position ein Wikilink ist
                resolved_path = self._document.resolve_wikilink_at_position(char_pos)
                if resolved_path:
                    # Wikilink gefunden - Navigation anfordern
                    self.wikilink_requested.emit(resolved_path)
                    return  # Event nicht weiterleiten

        # Standard-Verhalten für alle anderen Clicks
        QsciScintilla.mousePressEvent(self._editor, event)