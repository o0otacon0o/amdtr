"""
SearchPalette — QDialog-Overlay für die Volltextsuche im Workspace.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QFont

from core.workspace import Workspace


class SearchPalette(QDialog):
    """
    Volltextsuche-Overlay.
    
    Keyboard-Shortcuts:
    - Ctrl+Shift+F: Öffnen
    - Escape: Schließen
    - Enter: Datei öffnen
    - Up/Down: Navigation
    """
    
    # Signals
    file_requested = pyqtSignal(Path)
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._workspace: Workspace | None = None
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_debounce()
    
    def _setup_ui(self) -> None:
        self.setWindowTitle("Global Search")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.resize(700, 500)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._input = QLineEdit()
        self._input.setPlaceholderText("Full-text search in workspace...")
        self._input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                font-size: 14px;
                border: none;
                border-bottom: 1px solid #e1e4e8;
            }
        """)
        layout.addWidget(self._input)
        
        self._results = QListWidget()
        self._results.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #f6f8fa;
            }
        """)
        layout.addWidget(self._results)
        
        self.setLayout(layout)
        
        self._input.textChanged.connect(self._on_text_changed)
        self._results.itemDoubleClicked.connect(self._on_item_activated)
    
    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self._on_item_activated)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self).activated.connect(self._navigate_up)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self).activated.connect(self._navigate_down)
    
    def _setup_debounce(self) -> None:
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._update_results)
    
    def _navigate_up(self) -> None:
        current = self._results.currentRow()
        if current > 0:
            self._results.setCurrentRow(current - 1)
    
    def _navigate_down(self) -> None:
        current = self._results.currentRow()
        if current < self._results.count() - 1:
            self._results.setCurrentRow(current + 1)

    def set_workspace(self, workspace: Workspace | None) -> None:
        self._workspace = workspace

    def _on_text_changed(self) -> None:
        self._search_timer.stop()
        self._search_timer.start(150)  # Längeres Debounce für DB-Suche
    
    def _update_results(self) -> None:
        if not self._workspace:
            return
            
        query = self._input.text().strip()
        if not query:
            self._results.clear()
            return
            
        # SQLite Suche ausführen
        results = self._workspace.index.search(query)
        
        self._results.clear()
        for path_str, title, excerpt in results:
            item = QListWidgetItem()
            
            # Formatiertes Snippet (HTML-ähnlich via Rich Text)
            # Wir ersetzen die == Marker durch Fettdruck
            clean_excerpt = excerpt.replace("==", "<b>").replace("==", "</b>")
            
            display_text = f"<b>{title}</b><br/><small style='color: #666;'>{clean_excerpt}</small>"
            
            label = QLabel(display_text)
            label.setContentsMargins(5, 2, 5, 2)
            label.setWordWrap(True)
            
            item.setSizeHint(label.sizeHint())
            self._results.addItem(item)
            self._results.setItemWidget(item, label)
            item.setData(Qt.ItemDataRole.UserRole, path_str)
        
        if self._results.count() > 0:
            self._results.setCurrentRow(0)
    
    def _on_item_activated(self) -> None:
        current_item = self._results.currentItem()
        if not current_item:
            return
        
        path_str = current_item.data(Qt.ItemDataRole.UserRole)
        self.file_requested.emit(Path(path_str))
        self.close()
    
    def open_search(self) -> None:
        self._input.clear()
        self._results.clear()
        self.show()
        self._input.setFocus()
    
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + 50  # Fixer Offset von oben
            self.move(x, y)
