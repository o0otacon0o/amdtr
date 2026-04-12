"""
MdMermaidLexer — Custom Markdown + Mermaid Lexer für QScintilla.

Implementiert Syntax-Highlighting für Markdown mit spezieller
Unterstützung für Mermaid-Diagramme und Code-Blöcke.
"""

from __future__ import annotations
from typing import Optional
import re
from PyQt6.Qsci import QsciLexerCustom, QsciScintilla
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont


from themes.schema import EditorTheme, TokenStyle


class TokenType:
    """Token-Kategorien für Markdown-Highlighting."""
    DEFAULT = 0
    HEADING_1 = 1
    HEADING_2 = 2
    HEADING_3 = 3
    HEADING_4 = 4
    HEADING_5 = 5
    HEADING_6 = 6
    BOLD = 7
    ITALIC = 8
    BOLD_ITALIC = 9
    INLINE_CODE = 10
    CODE_FENCE = 11
    MERMAID_FENCE = 12
    LINK_TEXT = 13
    LINK_URL = 14
    WIKILINK = 15        # [[wikilink]] Syntax
    WIKILINK_BROKEN = 16 # [[broken-link]] nicht auflösbar
    BLOCKQUOTE = 17
    LIST_MARKER = 18
    HR = 19
    FRONTMATTER = 20


class LexerState:
    """Zustände für mehrzeilige Blöcke."""
    NORMAL = 0
    CODE_BLOCK = 1
    MERMAID_BLOCK = 2
    FRONTMATTER = 3


class MdMermaidLexer(QsciLexerCustom):
    """
    Custom Lexer für Markdown + Mermaid.
    
    Erbt von QsciLexerCustom und implementiert styleText()
    für eigenes Syntax-Highlighting.
    """
    
    def __init__(self, parent: Optional[QsciScintilla] = None) -> None:
        super().__init__(parent)
        self._theme: Optional[EditorTheme] = None
        self._setup_patterns()
        self._setup_default_styles()
        
    def set_theme(self, theme: EditorTheme) -> None:
        """Aktualisiert das Theme des Lexers."""
        self._theme = theme
        self._apply_theme_styles()
        
    def _apply_theme_styles(self) -> None:
        """Überträgt Theme-Farben auf den Lexer."""
        if not self._theme:
            return
            
        # Token-Mapping (Schema-Keys zu TokenType)
        mapping = {
            "DEFAULT": TokenType.DEFAULT,
            "HEADING_1": TokenType.HEADING_1,
            "HEADING_2": TokenType.HEADING_2,
            "HEADING_3": TokenType.HEADING_3,
            "HEADING_4": TokenType.HEADING_4,
            "HEADING_5": TokenType.HEADING_5,
            "HEADING_6": TokenType.HEADING_6,
            "BOLD": TokenType.BOLD,
            "ITALIC": TokenType.ITALIC,
            "BOLD_ITALIC": TokenType.BOLD_ITALIC,
            "INLINE_CODE": TokenType.INLINE_CODE,
            "CODE_FENCE": TokenType.CODE_FENCE,
            "MERMAID_FENCE": TokenType.MERMAID_FENCE,
            "LINK_TEXT": TokenType.LINK_TEXT,
            "LINK_URL": TokenType.LINK_URL,
            "WIKILINK": TokenType.WIKILINK,
            "WIKILINK_BROKEN": TokenType.WIKILINK_BROKEN,
            "BLOCKQUOTE": TokenType.BLOCKQUOTE,
            "LIST_MARKER": TokenType.LIST_MARKER,
            "HR": TokenType.HR,
            "FRONTMATTER": TokenType.FRONTMATTER,
        }
        
        # Basis-Font vom Editor holen (falls vorhanden)
        base_font = QFont()
        if self.editor():
            base_font = self.editor().font()

        for key, token_type in mapping.items():
            style = self._theme.tokens.get(key)
            if style:
                color = QColor(style.color)
                self._default_colors[token_type] = color
                
                # Explizit an QsciLexer übertragen
                self.setColor(color, token_type)
                
                # Hintergrund für Token
                if style.background:
                    self.setPaper(QColor(style.background), token_type)
                else:
                    self.setPaper(QColor(self._theme.background), token_type)
                
                # Font-Attribute
                font = QFont(base_font)
                if style.bold:
                    font.setWeight(QFont.Weight.Bold)
                if style.italic:
                    font.setItalic(True)
                
                # Spezial-Fonts
                if key in ["INLINE_CODE", "CODE_FENCE", "MERMAID_FENCE"]:
                    font.setFixedPitch(True)
                    font.setFamily("monospace")
                
                self.setFont(font, token_type)
                self._font_attributes[token_type] = {
                    'weight': QFont.Weight.Bold if style.bold else QFont.Weight.Normal,
                    'italic': style.italic
                }

    def _setup_patterns(self) -> None:
        """Initialisiert Regex-Pattern für Token-Erkennung."""
        # Headings: # ## ### #### ##### ######
        self._heading_patterns = [
            (re.compile(r'^#{' + str(i) + r'}\s+.*$'), getattr(TokenType, f'HEADING_{i}'))
            for i in range(1, 7)
        ]
        
        # Block-Starts
        self._code_fence_start = re.compile(r'^```\w*$')
        self._mermaid_fence_start = re.compile(r'^```mermaid$')
        self._code_fence_end = re.compile(r'^```$')
        self._frontmatter_sep = re.compile(r'^---$')
        
        # Inline-Formatierung
        # Reihenfolge bestimmt Priorität
        self._inline_patterns = [
            (re.compile(r'(\*\*\*([^*]+)\*\*\*)'), TokenType.BOLD_ITALIC),
            (re.compile(r'(\*\*([^*]+)\*\*)'), TokenType.BOLD),
            (re.compile(r'(\*([^*]+)\*)'), TokenType.ITALIC),
            (re.compile(r'(`([^`]+)`)'), TokenType.INLINE_CODE),
            (re.compile(r'(\[([^\]]+)\]\(([^)]+)\))'), TokenType.LINK_TEXT),
            (re.compile(r'(\[\[([^\[\]]+)\]\])'), TokenType.WIKILINK),
            (re.compile(r'^(\s*[-*+]\s+)'), TokenType.LIST_MARKER),
        ]
        
        # Blockquotes: >
        self._blockquote_pattern = re.compile(r'^>\s+.*$')
        
        # Horizontale Linien: --- *** ___
        self._hr_pattern = re.compile(r'^(-{3,}|\*{3,}|_{3,})$')
    
    def _setup_default_styles(self) -> None:
        """Setzt Standard-Farben für alle Token-Typen."""
        self._default_colors = {
            TokenType.DEFAULT: QColor("#24292f"),
            TokenType.HEADING_1: QColor("#0969da"),
            TokenType.HEADING_2: QColor("#0969da"),
            TokenType.HEADING_3: QColor("#0969da"),
            TokenType.HEADING_4: QColor("#656d76"),
            TokenType.HEADING_5: QColor("#656d76"),
            TokenType.HEADING_6: QColor("#656d76"),
            TokenType.BOLD: QColor("#24292f"),
            TokenType.ITALIC: QColor("#24292f"),
            TokenType.BOLD_ITALIC: QColor("#24292f"),
            TokenType.INLINE_CODE: QColor("#af3d10"),
            TokenType.CODE_FENCE: QColor("#6e7781"),
            TokenType.MERMAID_FENCE: QColor("#8250df"),
            TokenType.LINK_TEXT: QColor("#0969da"),
            TokenType.LINK_URL: QColor("#6e7781"),
            TokenType.WIKILINK: QColor("#0969da"),
            TokenType.WIKILINK_BROKEN: QColor("#cf222e"),
            TokenType.BLOCKQUOTE: QColor("#6e7781"),
            TokenType.LIST_MARKER: QColor("#0969da"),
            TokenType.HR: QColor("#d0d7de"),
            TokenType.FRONTMATTER: QColor("#6e7781"),
        }
        
        self._font_attributes = {
            TokenType.HEADING_1: {'weight': QFont.Weight.Bold},
            TokenType.HEADING_2: {'weight': QFont.Weight.Bold},
            TokenType.HEADING_3: {'weight': QFont.Weight.Bold},
            TokenType.BOLD: {'weight': QFont.Weight.Bold},
            TokenType.BOLD_ITALIC: {'weight': QFont.Weight.Bold, 'italic': True},
            TokenType.ITALIC: {'italic': True},
            TokenType.INLINE_CODE: {'family': 'monospace'},
            TokenType.CODE_FENCE: {'family': 'monospace'},
            TokenType.MERMAID_FENCE: {'family': 'monospace'},
        }
    
    def language(self) -> str:
        return "Markdown"
    
    def description(self, style: int) -> str:
        descriptions = {
            TokenType.DEFAULT: "Default",
            TokenType.HEADING_1: "Heading 1",
            TokenType.HEADING_2: "Heading 2", 
            TokenType.HEADING_3: "Heading 3",
            TokenType.HEADING_4: "Heading 4",
            TokenType.HEADING_5: "Heading 5",
            TokenType.HEADING_6: "Heading 6",
            TokenType.BOLD: "Bold",
            TokenType.ITALIC: "Italic",
            TokenType.BOLD_ITALIC: "Bold Italic",
            TokenType.INLINE_CODE: "Inline Code",
            TokenType.CODE_FENCE: "Code Block",
            TokenType.MERMAID_FENCE: "Mermaid Diagram",
            TokenType.LINK_TEXT: "Link Text",
            TokenType.LINK_URL: "Link URL",
            TokenType.WIKILINK: "Wikilink",
            TokenType.WIKILINK_BROKEN: "Broken Wikilink",
            TokenType.BLOCKQUOTE: "Blockquote",
            TokenType.LIST_MARKER: "List Marker",
            TokenType.HR: "Horizontal Rule",
            TokenType.FRONTMATTER: "Front Matter",
        }
        return descriptions.get(style, "Unknown")
    
    def defaultColor(self, style: int) -> QColor:
        return self._default_colors.get(style, QColor("#000000"))
    
    def styleText(self, start: int, end: int) -> None:
        """
        Haupt-Styling-Methode. Wird von QScintilla aufgerufen.
        """
        if not self.editor():
            return
            
        # Bestimme die Zeile, an der das Styling beginnt
        start_line, _ = self.editor().lineIndexFromPosition(start)
        
        # Zustand der vorherigen Zeile holen
        state = LexerState.NORMAL
        if start_line > 0:
            state = self.editor().SendScintilla(QsciScintilla.SCI_GETLINESTATE, start_line - 1)
            if state == -1: # Uninitialisiert
                state = LexerState.NORMAL
        
        # Wir beginnen das Styling am Anfang der Zeile
        current_pos = self.editor().positionFromLineIndex(start_line, 0)
        self.startStyling(current_pos)
        
        current_line = start_line
        last_line = self.editor().lines() - 1
        
        while current_pos < end or (current_line <= last_line and state != LexerState.NORMAL):
            line_text = self.editor().text(current_line)
            if line_text is None:
                break
                
            # WICHTIG: Byte-Länge für UTF-8 berechnen
            line_bytes = line_text.encode('utf-8')
            line_len = len(line_bytes)
            
            # --- State Machine Logic ---
            new_state = state
            stripped = line_text.strip()
            
            if state == LexerState.NORMAL:
                if self._mermaid_fence_start.match(stripped):
                    new_state = LexerState.MERMAID_BLOCK
                    self.setStyling(line_len, TokenType.MERMAID_FENCE)
                elif self._code_fence_start.match(stripped):
                    new_state = LexerState.CODE_BLOCK
                    self.setStyling(line_len, TokenType.CODE_FENCE)
                elif current_line == 0 and self._frontmatter_sep.match(stripped):
                    new_state = LexerState.FRONTMATTER
                    self.setStyling(line_len, TokenType.FRONTMATTER)
                else:
                    # Normales Zeilen-Styling (Markdown)
                    self._style_markdown_line(line_text, line_bytes, current_pos)
                    
            elif state == LexerState.MERMAID_BLOCK:
                self.setStyling(line_len, TokenType.MERMAID_FENCE)
                if self._code_fence_end.match(stripped):
                    new_state = LexerState.NORMAL
                    
            elif state == LexerState.CODE_BLOCK:
                self.setStyling(line_len, TokenType.CODE_FENCE)
                if self._code_fence_end.match(stripped):
                    new_state = LexerState.NORMAL
                    
            elif state == LexerState.FRONTMATTER:
                self.setStyling(line_len, TokenType.FRONTMATTER)
                if current_line > 0 and self._frontmatter_sep.match(stripped):
                    new_state = LexerState.NORMAL

            # State für die Zeile speichern
            self.editor().SendScintilla(QsciScintilla.SCI_SETLINESTATE, current_line, new_state)
            
            state = new_state
            current_pos += line_len
            current_line += 1
            
            if current_line > last_line:
                break

    def _style_markdown_line(self, text: str, line_bytes: bytes, line_start_pos: int) -> None:
        """Stylt eine einzelne Zeile Markdown-Text (Byte-basiert)."""
        line_len = len(line_bytes)
        stripped = text.strip()
        
        # 1. Block-Level (Headings, HR, Blockquotes)
        # Headings
        for pattern, token_type in self._heading_patterns:
            if pattern.match(stripped):
                self.setStyling(line_len, token_type)
                return
                
        # Blockquotes
        if self._blockquote_pattern.match(stripped):
            self.setStyling(line_len, TokenType.BLOCKQUOTE)
            return
            
        # HR
        if self._hr_pattern.match(stripped):
            self.setStyling(line_len, TokenType.HR)
            return
            
        # 2. Inline-Level (Mixed Styles) - One-Pass Forward Styling
        matches = []
        for pattern, token_type in self._inline_patterns:
            for match in pattern.finditer(text):
                # Umrechnung: Zeichen-Index -> Byte-Index (UTF-8)
                b_start = len(text[:match.start()].encode('utf-8'))
                b_end = len(text[:match.end()].encode('utf-8'))
                matches.append((b_start, b_end, token_type))
        
        # Sortieren: Erst nach Start-Position, dann nach Länge (längere zuerst)
        matches.sort(key=lambda x: (x[0], -x[1]))
        
        # Styling-Schleife (Forward only)
        last_pos = 0
        for s, e, t in matches:
            if s < last_pos:
                continue # Überlappung vermeiden
                
            # Gap davor mit DEFAULT füllen
            if s > last_pos:
                self.setStyling(s - last_pos, TokenType.DEFAULT)
            
            # Token stylen
            self.setStyling(e - s, t)
            last_pos = e
            
        # Rest der Zeile mit DEFAULT füllen
        if last_pos < line_len:
            self.setStyling(line_len - last_pos, TokenType.DEFAULT)
