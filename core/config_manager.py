"""
ConfigManager — Verwaltung der Anwendungseinstellungen.

Kapselt:
- QSettings für systemweite Einstellungen
- Workspace-spezifische Konfiguration
- Theme-Einstellungen
- Editor-Präferenzen
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any, Optional
from PyQt6.QtCore import QSettings


@dataclass
class EditorConfig:
    """Editor-spezifische Einstellungen."""
    font_family: str = "Cascadia Code"
    font_size: int = 11
    tab_width: int = 4
    line_numbers: bool = True
    word_wrap: bool = False
    vim_mode: bool = False
    auto_save: bool = True
    auto_save_delay: int = 2000  # milliseconds


@dataclass
class UIConfig:
    """UI-spezifische Einstellungen."""
    theme_name: str = "github-light"
    sidebar_width: int = 260
    preview_enabled: bool = True
    show_outline: bool = True
    window_geometry: bytes = b""
    splitter_state: bytes = b""


@dataclass
class AppConfig:
    """Globale Anwendungseinstellungen."""
    last_workspace: str = ""
    recent_files: list[str] = None
    recent_workspaces: list[str] = None
    editor: EditorConfig = None
    ui: UIConfig = None
    
    def __post_init__(self):
        if self.recent_files is None:
            self.recent_files = []
        if self.recent_workspaces is None:
            self.recent_workspaces = []
        if self.editor is None:
            self.editor = EditorConfig()
        if self.ui is None:
            self.ui = UIConfig()


class ConfigManager:
    """
    Zentrale Konfigurationsverwaltung.
    
    Verwaltet sowohl globale App-Einstellungen (QSettings)
    als auch workspace-spezifische Konfigurationen.
    """
    
    def __init__(self) -> None:
        self._settings = QSettings("amdtr", "app")
        self._config = self._load_config()
        
    @property
    def config(self) -> AppConfig:
        """Aktuelle Konfiguration."""
        return self._config
    
    def save_config(self) -> None:
        """Speichert aktuelle Konfiguration persistent."""
        # Editor-Einstellungen
        editor = self._config.editor
        self._settings.beginGroup("editor")
        self._settings.setValue("font_family", editor.font_family)
        self._settings.setValue("font_size", editor.font_size)
        self._settings.setValue("tab_width", editor.tab_width)
        self._settings.setValue("line_numbers", editor.line_numbers)
        self._settings.setValue("word_wrap", editor.word_wrap)
        self._settings.setValue("vim_mode", editor.vim_mode)
        self._settings.setValue("auto_save", editor.auto_save)
        self._settings.setValue("auto_save_delay", editor.auto_save_delay)
        self._settings.endGroup()
        
        # UI-Einstellungen
        ui = self._config.ui
        self._settings.beginGroup("ui")
        self._settings.setValue("theme_name", ui.theme_name)
        self._settings.setValue("sidebar_width", ui.sidebar_width)
        self._settings.setValue("preview_enabled", ui.preview_enabled)
        self._settings.setValue("show_outline", ui.show_outline)
        self._settings.setValue("window_geometry", ui.window_geometry)
        self._settings.setValue("splitter_state", ui.splitter_state)
        self._settings.endGroup()
        
        # Globale Einstellungen
        self._settings.setValue("last_workspace", self._config.last_workspace)
        self._settings.setValue("recent_files", self._config.recent_files)
        self._settings.setValue("recent_workspaces", self._config.recent_workspaces)
        
        self._settings.sync()
    
    def add_recent_file(self, path: Path) -> None:
        """Fügt eine Datei zur Recent-Liste hinzu."""
        path_str = str(path)
        
        # Vorhandenen Eintrag entfernen
        if path_str in self._config.recent_files:
            self._config.recent_files.remove(path_str)
            
        # An den Anfang hinzufügen
        self._config.recent_files.insert(0, path_str)
        
        # Auf max. 10 Einträge begrenzen
        self._config.recent_files = self._config.recent_files[:10]
    
    def add_recent_workspace(self, path: Path) -> None:
        """Fügt einen Workspace zur Recent-Liste hinzu."""
        path_str = str(path)
        
        # Vorhandenen Eintrag entfernen
        if path_str in self._config.recent_workspaces:
            self._config.recent_workspaces.remove(path_str)
            
        # An den Anfang hinzufügen
        self._config.recent_workspaces.insert(0, path_str)
        
        # Auf max. 5 Einträge begrenzen
        self._config.recent_workspaces = self._config.recent_workspaces[:5]
    
    def get_workspace_config_path(self, workspace_root: Path) -> Path:
        """
        Pfad zur workspace-spezifischen Konfigurationsdatei.
        Liegt in .amdtr/config.toml
        """
        return workspace_root / ".amdtr" / "config.toml"
    
    def _load_config(self) -> AppConfig:
        """Lädt Konfiguration aus QSettings."""
        config = AppConfig()
        
        # Editor-Einstellungen laden
        self._settings.beginGroup("editor")
        config.editor.font_family = self._settings.value("font_family", config.editor.font_family)
        config.editor.font_size = int(self._settings.value("font_size", config.editor.font_size))
        config.editor.tab_width = int(self._settings.value("tab_width", config.editor.tab_width))
        config.editor.line_numbers = self._settings.value("line_numbers", config.editor.line_numbers, type=bool)
        config.editor.word_wrap = self._settings.value("word_wrap", config.editor.word_wrap, type=bool)
        config.editor.vim_mode = self._settings.value("vim_mode", config.editor.vim_mode, type=bool)
        config.editor.auto_save = self._settings.value("auto_save", config.editor.auto_save, type=bool)
        config.editor.auto_save_delay = int(self._settings.value("auto_save_delay", config.editor.auto_save_delay))
        self._settings.endGroup()
        
        # UI-Einstellungen laden
        self._settings.beginGroup("ui")
        config.ui.theme_name = self._settings.value("theme_name", config.ui.theme_name)
        config.ui.sidebar_width = int(self._settings.value("sidebar_width", config.ui.sidebar_width))
        config.ui.preview_enabled = self._settings.value("preview_enabled", config.ui.preview_enabled, type=bool)
        config.ui.show_outline = self._settings.value("show_outline", config.ui.show_outline, type=bool)
        config.ui.window_geometry = self._settings.value("window_geometry", config.ui.window_geometry)
        config.ui.splitter_state = self._settings.value("splitter_state", config.ui.splitter_state)
        self._settings.endGroup()
        
        # Globale Einstellungen laden
        config.last_workspace = self._settings.value("last_workspace", "")
        config.recent_files = self._settings.value("recent_files", [], type=list)
        config.recent_workspaces = self._settings.value("recent_workspaces", [], type=list)
        
        return config