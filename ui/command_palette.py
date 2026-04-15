"""
Command Palette — QDialog-Overlay für schnelle Navigation.

VSCode-inspired Command Palette mit:
- Fuzzy-Search für Dateien und Aktionen  
- Keyboard-Navigation (Up/Down, Enter, Escape)
- Datenquellen: .md Dateien, Aktionen, kürzliche Dokumente
- Präfixe: ":>" für Aktionen, normale Eingabe für Dateien
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QFont

from core.fuzzy_matcher import fuzzy_match, FuzzyMatch
from core.workspace import Workspace


class CommandItem:
    """Ein Item in der Command Palette (Datei oder Aktion)."""
    
    def __init__(self, 
                 title: str, 
                 subtitle: str = "",
                 action: Callable[[], None] | None = None,
                 file_path: Path | None = None):
        self.title = title
        self.subtitle = subtitle
        self.action = action
        self.file_path = file_path
        
    @property 
    def display_text(self) -> str:
        """Text für Fuzzy-Matching und Anzeige."""
        if self.subtitle:
            return f"{self.title} — {self.subtitle}"
        return self.title
    
    @property
    def is_action(self) -> bool:
        return self.action is not None
    
    @property 
    def is_file(self) -> bool:
        return self.file_path is not None


class CommandPalette(QDialog):
    """
    Command Palette Dialog — VSCode-style Quick Open.
    
    Keyboard-Shortcuts:
    - Ctrl+P: Dateien + Aktionen
    - Ctrl+Shift+P: Nur Aktionen
    - Escape: Schließen
    - Enter: Item ausführen
    - Up/Down: Navigation
    """
    
    # Signals
    file_requested = pyqtSignal(Path)  # User möchte Datei öffnen
    action_requested = pyqtSignal(str)  # User möchte Aktion ausführen
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._workspace: Workspace | None = None
        self._all_items: list[CommandItem] = []
        self._actions_only_mode = False
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_debounce()
        
        # Basis-Aktionen definieren
        self._register_default_actions()
    
    # ── UI Setup ──────────────────────────────────────────────────────
    
    def _setup_ui(self) -> None:
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.resize(600, 400)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Input Field
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type to search files and commands...")
        layout.addWidget(self._input)
        
        # Results List  
        self._results = QListWidget()
        layout.addWidget(self._results)
        
        self.setLayout(layout)
        
        # Event-Verbindungen
        self._input.textChanged.connect(self._on_text_changed)
        self._results.itemDoubleClicked.connect(self._on_item_activated)
    
    def set_theme(self, theme: Any) -> None:
        """Applies theme to the palette."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.ui.sidebar_bg};
                border: 1px solid {theme.ui.border};
            }}
            QLineEdit {{
                padding: 12px;
                font-size: 14px;
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border: none;
                border-bottom: 1px solid {theme.ui.border};
            }}
            QListWidget {{
                background-color: {theme.ui.sidebar_bg};
                color: {theme.ui.sidebar_fg};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {theme.ui.border};
            }}
            QListWidget::item:selected {{
                background-color: {theme.ui.button_bg};
                color: {theme.preview.link};
            }}
        """)
    
    def _setup_shortcuts(self) -> None:
        # Enter: Item ausführen
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self._on_item_activated)
        
        # Escape: Schließen  
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.close)
        
        # Up/Down: Navigation in Liste
        up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        up_shortcut.activated.connect(self._navigate_up)
        
        down_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        down_shortcut.activated.connect(self._navigate_down)
    
    def _setup_debounce(self) -> None:
        """Debounce Timer für flüssige Suche während dem Tippen."""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._update_results)
    
    # ── Navigation ────────────────────────────────────────────────────
    
    def _navigate_up(self) -> None:
        current = self._results.currentRow()
        if current > 0:
            self._results.setCurrentRow(current - 1)
        elif self._results.count() > 0:
            self._results.setCurrentRow(self._results.count() - 1)  # Wrap around
    
    def _navigate_down(self) -> None:
        current = self._results.currentRow()
        if current < self._results.count() - 1:
            self._results.setCurrentRow(current + 1)
        else:
            self._results.setCurrentRow(0)  # Wrap around
    
    # ── Datenquellen ──────────────────────────────────────────────────
    
    def set_workspace(self, workspace: Workspace | None) -> None:
        """Setzt den aktiven Workspace für Datei-Suche."""
        self._workspace = workspace
        self._rebuild_items()
    
    def _register_default_actions(self) -> None:
        """Registriert Standard-Aktionen."""
        self._default_actions = [
            CommandItem(
                ":> Open Workspace",
                "Open a folder as workspace",
                lambda: self.action_requested.emit("open_workspace")
            ),
            CommandItem(
                ":> Open File",
                "Open a single markdown file", 
                lambda: self.action_requested.emit("open_file")
            ),
            CommandItem(
                ":> Save All",
                "Save all open files",
                lambda: self.action_requested.emit("save_all")
            ),
            CommandItem(
                ":> Toggle Sidebar",
                "Show/hide the file tree",
                lambda: self.action_requested.emit("toggle_sidebar")
            ),
            CommandItem(
                ":> Toggle Vim Mode",
                "Toggle experimental Vim modal editing",
                lambda: self.action_requested.emit("toggle_vim")
            ),
        ]
    
    def _rebuild_items(self) -> None:
        """Baut die komplette Item-Liste neu auf."""
        self._all_items = []
        
        # Aktionen hinzufügen
        self._all_items.extend(self._default_actions)
        
        # Dateien hinzufügen (nur wenn nicht Actions-Only-Modus)
        if not self._actions_only_mode and self._workspace:
            for note_path in self._workspace.all_notes():
                relative_path = self._workspace.relative(note_path)
                item = CommandItem(
                    note_path.stem,
                    str(relative_path),
                    file_path=note_path
                )
                self._all_items.append(item)
    
    # ── Search & Results ───────────────────────────────────────────────
    
    def _on_text_changed(self) -> None:
        """Startet verzögerte Suche nach Texteingabe."""
        self._search_timer.stop()
        self._search_timer.start(50)  # 50ms Debounce
    
    def _update_results(self) -> None:
        """Aktualisiert Suchergebnisse basierend auf Input."""
        query = self._input.text().strip()
        
        # Items filtern basierend auf Modus
        items_to_search = []
        if self._actions_only_mode:
            # Nur Aktionen
            items_to_search = [item for item in self._all_items if item.is_action]
        else:
            # Alle Items, aber Actions-Präfix berücksichtigen
            if query.startswith(":>"):
                query = query[2:].strip()
                items_to_search = [item for item in self._all_items if item.is_action]
            else:
                items_to_search = self._all_items
        
        # Fuzzy-Matching
        candidates = [(item.display_text, item) for item in items_to_search]
        matches = fuzzy_match(query, candidates)
        
        # Results-Liste aktualisieren
        self._results.clear()
        for match in matches[:20]:  # Maximal 20 Ergebnisse
            self._add_result_item(match)
        
        # Erstes Item auswählen
        if self._results.count() > 0:
            self._results.setCurrentRow(0)
    
    def _add_result_item(self, match: FuzzyMatch) -> None:
        """Fügt ein Suchergebnis zur Liste hinzu."""
        item: CommandItem = match.item
        
        list_item = QListWidgetItem()
        
        # Verschiedene Icons/Präfixe für verschiedene Item-Typen
        if item.is_action:
            title = f"> {item.title}"
        elif item.is_file:
            title = f"• {item.title}"
        else:
            title = item.title
        
        if item.subtitle:
            text = f"{title}\n{item.subtitle}"
        else:
            text = title
            
        list_item.setText(text)
        list_item.setData(Qt.ItemDataRole.UserRole, item)
        
        self._results.addItem(list_item)
    
    def _on_item_activated(self) -> None:
        """Führt das aktuell ausgewählte Item aus."""
        current_item = self._results.currentItem()
        if not current_item:
            return
        
        command_item: CommandItem = current_item.data(Qt.ItemDataRole.UserRole)
        
        if command_item.is_action and command_item.action:
            command_item.action()
        elif command_item.is_file and command_item.file_path:
            self.file_requested.emit(command_item.file_path)
        
        self.close()
    
    # ── Public Interface ───────────────────────────────────────────────
    
    def show_files_and_actions(self) -> None:
        """Zeigt Command Palette für Dateien und Aktionen (Ctrl+P)."""
        self._actions_only_mode = False
        self._input.setPlaceholderText("Type to search files and commands...")
        self._rebuild_items()
        self._input.clear()
        self.show()
        self._input.setFocus()
        self._update_results()
    
    def show_actions_only(self) -> None:
        """Zeigt Command Palette nur für Aktionen (Ctrl+Shift+P)."""
        self._actions_only_mode = True
        self._input.setPlaceholderText("Type to search commands...")
        self._rebuild_items()
        self._input.clear()
        self.show()
        self._input.setFocus()
        self._update_results()
    
    def showEvent(self, event) -> None:
        """Zentriert Dialog beim Anzeigen."""
        super().showEvent(event)
        if self.parent():
            # Zentriert über Parent-Window
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + parent_geo.height() // 4  # Etwas oberhalb der Mitte
            self.move(x, y)