"""
Theme Schema — Datenstrukturen für JSON-Theme-Definitionen.

Definiert die Struktur und Validation für Theme-Files.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class TokenStyle:
    """Style-Definition für einen Token-Typ."""
    color: str
    background: Optional[str] = None
    bold: bool = False
    italic: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TokenStyle:
        """Erstellt TokenStyle aus Dictionary."""
        return cls(
            color=data.get("color", "#000000"),
            background=data.get("background"),
            bold=data.get("bold", False),
            italic=data.get("italic", False)
        )


@dataclass
class EditorTheme:
    """Editor-spezifische Theme-Definition."""
    background: str
    foreground: str
    selection_bg: str
    selection_fg: str
    line_number_bg: str
    line_number_fg: str
    current_line: str
    tokens: Dict[str, TokenStyle]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EditorTheme:
        """Erstellt EditorTheme aus Dictionary."""
        tokens = {}
        for token_name, token_data in data.get("tokens", {}).items():
            tokens[token_name] = TokenStyle.from_dict(token_data)
            
        return cls(
            background=data.get("background", "#ffffff"),
            foreground=data.get("foreground", "#000000"), 
            selection_bg=data.get("selection_bg", "#316ac5"),
            selection_fg=data.get("selection_fg", "#ffffff"),
            line_number_bg=data.get("line_number_bg", "#f6f8fa"),
            line_number_fg=data.get("line_number_fg", "#656d76"),
            current_line=data.get("current_line", "#f6f8fa"),
            tokens=tokens
        )


@dataclass 
class UITheme:
    """UI-spezifische Theme-Definition."""
    sidebar_bg: str
    sidebar_fg: str
    tab_active_bg: str
    tab_active_fg: str
    tab_inactive_bg: str
    tab_inactive_fg: str
    border: str
    button_bg: str
    button_fg: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UITheme:
        """Erstellt UITheme aus Dictionary.""" 
        return cls(
            sidebar_bg=data.get("sidebar_bg", "#f6f8fa"),
            sidebar_fg=data.get("sidebar_fg", "#24292f"),
            tab_active_bg=data.get("tab_active_bg", "#ffffff"),
            tab_active_fg=data.get("tab_active_fg", "#24292f"),
            tab_inactive_bg=data.get("tab_inactive_bg", "#f6f8fa"),
            tab_inactive_fg=data.get("tab_inactive_fg", "#656d76"),
            border=data.get("border", "#d1d9e0"),
            button_bg=data.get("button_bg", "#f6f8fa"),
            button_fg=data.get("button_fg", "#24292f")
        )


@dataclass
class PreviewTheme:
    """Preview-spezifische Theme-Definition."""
    background: str
    foreground: str
    link: str
    heading: str
    code_bg: str
    border: str
    syntax: str = "light"
    mermaid: str = "default"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PreviewTheme:
        """Erstellt PreviewTheme aus Dictionary."""
        return cls(
            background=data.get("background", "#ffffff"),
            foreground=data.get("foreground", "#000000"),
            link=data.get("link", "#0969da"),
            heading=data.get("heading", "#0969da"),
            code_bg=data.get("code-bg", data.get("code_bg", "#f6f8fa")),
            border=data.get("border", "#d1d9e0"),
            syntax=data.get("syntax", "light"),
            mermaid=data.get("mermaid", "default")
        )
    
    def to_dict(self) -> Dict[str, str]:
        """Gibt alle Properties als Dictionary für die CSS-Injektion zurück."""
        return {
            "--bg": self.background,
            "--text": self.foreground,
            "--link": self.link,
            "--heading": self.heading,
            "--code-bg": self.code_bg,
            "--border": self.border,
            "--syntax": self.syntax,
            "--mermaid": self.mermaid
        }
    
    def to_css(self) -> str:
        """Konvertiert zu CSS Custom Properties."""
        lines = [":root {"]
        for prop, value in self.to_dict().items():
            lines.append(f"  {prop}: {value};")
        lines.append("}")
        return "\n".join(lines)


@dataclass
class Theme:
    """Vollständige Theme-Definition."""
    name: str
    dark: bool
    editor: EditorTheme
    ui: UITheme
    preview: PreviewTheme
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Theme:
        """Erstellt Theme aus JSON-Dictionary."""
        return cls(
            name=data.get("name", "Unnamed"),
            dark=data.get("dark", False),
            editor=EditorTheme.from_dict(data.get("editor", {})),
            ui=UITheme.from_dict(data.get("ui", {})),
            preview=PreviewTheme.from_dict(data.get("preview", {}))
        )