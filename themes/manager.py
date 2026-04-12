"""
ThemeManager — Management and loading of themes.

Enables loading of JSON themes and switching at runtime.
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
    Central management for application themes.
    
    Signals:
    - theme_changed: Emitted when a new theme is activated.
    """
    theme_changed = pyqtSignal(Theme)
    
    def __init__(self) -> None:
        super().__init__()
        self._themes: Dict[str, Theme] = {}
        self._active_theme: Optional[Theme] = None
        
        # PyInstaller-Bundle Support: Determine resource path
        if getattr(sys, 'frozen', False):
            # If executed as EXE, themes are located in _MEIPASS/themes
            self._themes_dir = Path(sys._MEIPASS) / "themes"
        else:
            # In development mode, relative to the script
            self._themes_dir = Path(__file__).parent
            
        self._settings = QSettings("amdtr", "app")
        
        self.discover_themes()
        self._load_saved_theme()
        
    def discover_themes(self) -> None:
        """Searches for .json files in the themes directory."""
        for json_file in self._themes_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    theme = Theme.from_dict(data)
                    self._themes[theme.name] = theme
            except Exception as e:
                print(f"Error loading theme {json_file}: {e}")
                
    def _load_saved_theme(self) -> None:
        """Loads the theme saved in QSettings."""
        saved_name = self._settings.value("active_theme", "One Dark")
        if not self.set_active_theme(saved_name):
            # Fallback
            if "One Dark" in self._themes:
                self.set_active_theme("One Dark")
            elif self._themes:
                self.set_active_theme(list(self._themes.keys())[0])

    def get_theme_names(self) -> List[str]:
        """Returns names of all available themes."""
        return list(self._themes.keys())
        
    def get_theme(self, name: str) -> Optional[Theme]:
        """Returns a theme by name."""
        return self._themes.get(name)
        
    def set_active_theme(self, name: str) -> bool:
        """Activates a theme by name."""
        theme = self.get_theme(name)
        if theme:
            self._active_theme = theme
            self._settings.setValue("active_theme", name)
            self.theme_changed.emit(theme)
            return True
        return False
        
    def active_theme(self) -> Theme:
        """Returns the currently active theme (fallback to first available)."""
        if self._active_theme:
            return self._active_theme
            
        if self._themes:
            # Fallback: prefer One Dark, otherwise the first one
            if "One Dark" in self._themes:
                return self._themes["One Dark"]
            return list(self._themes.values())[0]
            
        # Hardcoded fallback (should never happen if One Dark exists)
        raise RuntimeError("No themes found and no fallback available.")
