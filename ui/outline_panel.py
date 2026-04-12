"""
OutlinePanel — zeigt das Inhaltsverzeichnis (ToC) des aktuellen Dokuments.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal


@dataclass
class HeaderItem:
    level: int
    text: str
    line: int


class OutlinePanel(QWidget):
    """
    Panel zur Anzeige der Dokumentstruktur.
    """
    header_clicked = pyqtSignal(int)  # Emittet die Zeilennummer

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(15)
        self._tree.setAnimated(True)
        self._tree.setStyleSheet("border: none; outline: none;")
        
        layout.addWidget(self._tree)
        
        self._tree.itemClicked.connect(self._on_item_clicked)

    def update_outline(self, text: str):
        """Extrahiert Header und baut den Baum neu auf."""
        self._tree.clear()
        
        headers = self._parse_headers(text)
        if not headers:
            return

        # Stack für die Baum-Hierarchie
        stack: list[tuple[int, QTreeWidgetItem]] = []

        for h in headers:
            item = QTreeWidgetItem([h.text])
            item.setData(0, Qt.ItemDataRole.UserRole, h.line)
            
            # Einrückung basierend auf Level
            while stack and stack[-1][0] >= h.level:
                stack.pop()
            
            if not stack:
                self._tree.addTopLevelItem(item)
            else:
                stack[-1][1].addChild(item)
                stack[-1][1].setExpanded(True)
            
            stack.append((h.level, item))

    def _parse_headers(self, text: str) -> list[HeaderItem]:
        """Sucht nach # Header-Zeilen."""
        headers = []
        lines = text.splitlines()
        
        # Regex für Markdown-Header (ignoriert Header in Code-Blöcken nicht perfekt, 
        # aber reicht für den Prototyp)
        header_re = re.compile(r'^(#{1,6})\s+(.+)$')
        
        for i, line in enumerate(lines):
            match = header_re.match(line)
            if match:
                level = len(match.group(1))
                content = match.group(2).strip()
                headers.append(HeaderItem(level=level, text=content, line=i))
        
        return headers

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line is not None:
            self.header_clicked.emit(line)
