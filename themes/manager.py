"""
ThemeManager — Verwaltung und Laden von Themes.

Ermöglicht das Laden von JSON-Themes und das Umschalten zur Laufzeit.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from themes.schema import Theme


class ThemeManager(QObject):
    """
    Zentrale Verwaltung für Anwendung-Themes.
    
    Signals:
    - theme_changed: Wird emittiert, wenn ein neues Theme aktiviert wird.
    """
    theme_changed = pyqtSignal(Theme)
    
    def __init__(self) -> None:
        super().__init__()
        self._themes: Dict[str, Theme] = {}
        self._active_theme: Optional[Theme] = None
        
        # PyInstaller-Bundle Support: Ressourcenpfad bestimmen
        if getattr(sys, 'frozen', False):
            # Wenn als EXE ausgeführt, liegen Themes unter _MEIPASS/themes
            self._themes_dir = Path(sys._MEIPASS) / "themes"
        else:
            # Im Entwicklungsmodus relativ zum Skript
            self._themes_dir = Path(__file__).parent
            
        self._settings = QSettings("amdtr", "app")
        
        self.discover_themes()
        self._load_saved_theme()
        
    def discover_themes(self) -> None:
        """Sucht nach .json Dateien im themes-Verzeichnis."""
        for json_file in self._themes_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    theme = Theme.from_dict(data)
                    self._themes[theme.name] = theme
            except Exception as e:
                print(f"Error loading theme {json_file}: {e}")
                
    def _load_saved_theme(self) -> None:
        """Lädt das in den QSettings gespeicherte Theme."""
        saved_name = self._settings.value("active_theme", "One Dark")
        if not self.set_active_theme(saved_name):
            # Fallback
            if "One Dark" in self._themes:
                self.set_active_theme("One Dark")
            elif self._themes:
                self.set_active_theme(list(self._themes.keys())[0])

    def get_theme_names(self) -> List[str]:
        """Gibt Namen aller verfügbaren Themes zurück."""
        return list(self._themes.keys())
        
    def get_theme(self, name: str) -> Optional[Theme]:
        """Gibt ein Theme nach Name zurück."""
        return self._themes.get(name)
        
    def set_active_theme(self, name: str) -> bool:
        """Aktiviert ein Theme nach Name."""
        theme = self.get_theme(name)
        if theme:
            self._active_theme = theme
            self._settings.setValue("active_theme", name)
            self.theme_changed.emit(theme)
            return True
        return False
        
    def active_theme(self) -> Theme:
        """Gibt das aktuell aktive Theme zurück (Fallback auf erstes verfügbares)."""
        if self._active_theme:
            return self._active_theme
            
        if self._themes:
            # Fallback: One Dark bevorzugen, sonst das erste
            if "One Dark" in self._themes:
                return self._themes["One Dark"]
            return list(self._themes.values())[0]
            
        # Hardcoded Fallback (sollte nie passieren wenn One Dark existiert)
        raise RuntimeError("No themes found and no fallback available.")
