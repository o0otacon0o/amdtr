"""
Theme Schema — Data structures for JSON theme definitions.

Defines the structure and validation for theme files.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class TokenStyle:
    """Style definition for a token type."""
    color: str
    background: Optional[str] = None
    bold: bool = False
    italic: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TokenStyle:
        """Creates TokenStyle from dictionary."""
        return cls(
            color=data.get("color", "#000000"),
            background=data.get("background"),
            bold=data.get("bold", False),
            italic=data.get("italic", False)
        )


@dataclass
class EditorTheme:
    """Editor-specific theme definition."""
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
        """Creates EditorTheme from dictionary."""
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
    """UI-specific theme definition."""
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
        """Creates UITheme from dictionary.""" 
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
    """Preview-specific theme definition."""
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
        """Creates PreviewTheme from dictionary."""
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
        """Returns all properties as a dictionary for CSS injection."""
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
        """Converts to CSS custom properties."""
        lines = [":root {"]
        for prop, value in self.to_dict().items():
            lines.append(f"  {prop}: {value};")
        lines.append("}")
        return "\n".join(lines)


@dataclass
class Theme:
    """Full theme definition."""
    name: str
    dark: bool
    editor: EditorTheme
    ui: UITheme
    preview: PreviewTheme
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Theme:
        """Creates Theme from JSON dictionary."""
        return cls(
            name=data.get("name", "Unnamed"),
            dark=data.get("dark", False),
            editor=EditorTheme.from_dict(data.get("editor", {})),
            ui=UITheme.from_dict(data.get("ui", {})),
            preview=PreviewTheme.from_dict(data.get("preview", {}))
        )
