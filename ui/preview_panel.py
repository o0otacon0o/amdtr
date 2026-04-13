"""
Preview Panel mit QWebEngineView für Live-Markdown-Rendering
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl, pyqtSignal, QTimer, Qt
from pathlib import Path
import json
import os
import sys

from themes.schema import PreviewTheme


class PreviewPanel(QWidget):
    """QWebEngineView-basiertes Preview-Panel für Markdown-Rendering"""
    
    # Signals für Scroll-Synchronisation
    scroll_to_line = pyqtSignal(int)  # Python → Editor: scrolle zu Zeile
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load-Status verwalten
        self._page_loaded = False
        self._web_engine_initialized = False
        self._pending_updates = []
        self._pending_base_path = None
        self._active_theme: PreviewTheme | None = None
        
        self._setup_ui()

    def _ensure_web_engine(self):
        """Lazy initialization of WebEngine."""
        if self._web_engine_initialized:
            return
            
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebEngineCore import QWebEnginePage
            
            self.QWebEngineView = QWebEngineView
            self.QWebEnginePage = QWebEnginePage
            
            # Replace placeholder with actual WebView
            self.placeholder.hide()
            self.web_view = self.QWebEngineView()
            self.layout().addWidget(self.web_view)
            
            self._setup_web_channel()
            self._load_preview_page()
            self._web_engine_initialized = True
        except ImportError as e:
            self.placeholder.setText(f"Error loading WebEngine: {e}")

    def set_theme(self, theme: PreviewTheme) -> None:
        """Wendet ein Preview-Theme (CSS-Variablen) an."""
        self._active_theme = theme
        if self._page_loaded and hasattr(self, 'bridge'):
            self.bridge.set_theme_vars(theme.to_dict())

    def set_base_path(self, path: Path) -> None:
        """Setzt den Basispfad für relative Ressourcen (Bilder, Links)."""
        if self._page_loaded and hasattr(self, 'bridge'):
            self.bridge.set_base_path(str(path.absolute()))
        else:
            self._pending_base_path = path

    def _setup_ui(self) -> None:
        """UI-Layout initialisieren"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.placeholder = QLabel("Initializing Preview Engine...")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.placeholder)
        
    def _setup_web_channel(self) -> None:
        """QWebChannel für Python ↔ JavaScript Kommunikation"""
        from preview.preview_bridge import PreviewBridge
        
        self.channel = QWebChannel()
        self.bridge = PreviewBridge(self)
        self.channel.registerObject('bridge', self.bridge)
        
        # Bridge Signals verbinden
        self.bridge.scroll_to_line_requested.connect(self.scroll_to_line.emit)
        
        # Channel mit WebView verbinden
        self.web_view.page().setWebChannel(self.channel)
        
        # Web-Page für JavaScript-Aufrufe an Bridge weitergeben
        self.bridge.set_web_page(self.web_view.page())
        
        print(f"[DEBUG] PreviewPanel: Web channel and bridge connected")
        
    def _load_preview_page(self) -> None:
        """Preview HTML-Template laden"""
        if getattr(sys, 'frozen', False):
            # Wenn als EXE ausgeführt, liegen Ressourcen unter _MEIPASS/resources
            resources_dir = Path(sys._MEIPASS) / "resources"
        else:
            # Im Entwicklungsmodus relativ zum Skript
            resources_dir = Path(__file__).parent.parent / "resources"
            
        preview_html = resources_dir / "preview.html"
        
        if preview_html.exists():
            # Signal für LoadFinished verbinden
            self.web_view.loadFinished.connect(self._on_page_loaded)
            
            url = QUrl.fromLocalFile(str(preview_html.absolute()))
            self.web_view.load(url)
        else:
            # Fallback: Minimal-HTML direkt laden
            self._load_fallback_html()
    
    def _load_fallback_html(self) -> None:
        """Fallback HTML wenn preview.html nicht existiert"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>amdtr Preview</title>
            <style>
                body { font-family: -apple-system, sans-serif; padding: 20px; }
                .loading { color: #666; font-style: italic; }
            </style>
        </head>
        <body>
            <div class="loading">Preview wird geladen...</div>
            <div id="content"></div>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
        
    def update_markdown(self, markdown_text: str, cursor_line: int = 0) -> None:
        """Markdown-Content an Preview senden"""
        if not self._web_engine_initialized:
            self._ensure_web_engine()
            self._pending_updates.append((markdown_text, cursor_line))
            return

        if not self._page_loaded:
            self._pending_updates.append((markdown_text, cursor_line))
            return
            
        if hasattr(self, 'bridge'):
            self.bridge.update_markdown(markdown_text)
            if cursor_line > 0:
                self.bridge.scroll_to_line(cursor_line)
            
    def _on_page_loaded(self, success: bool) -> None:
        """HTML-Seite wurde vollständig geladen"""
        if success:
            self._page_loaded = True
            
            # Theme anwenden falls schon gesetzt
            if self._active_theme:
                self.bridge.set_theme_vars(self._active_theme.to_dict())
            
            # Basispfad anwenden falls schon gesetzt
            if self._pending_base_path:
                self.bridge.set_base_path(str(self._pending_base_path.absolute()))
                self._pending_base_path = None

            # Pending Updates verarbeiten
            for markdown_text, cursor_line in self._pending_updates:
                if hasattr(self, 'bridge'):
                    self.bridge.update_markdown(markdown_text)
                    if cursor_line > 0:
                        self.bridge.scroll_to_line(cursor_line)
            
            self._pending_updates.clear()
            
    def scroll_to_line_number(self, line: int) -> None:
        """Preview zu bestimmter Zeilennummer scrollen"""
        if hasattr(self, 'bridge'):
            self.bridge.scroll_to_line(line)

    def find_text(self, text: str, forward: bool = True) -> None:
        """Sucht nach Text in der HTML-Vorschau."""
        if not self._web_engine_initialized:
            return

        options = self.QWebEnginePage.FindFlag(0)
        if not forward:
            options |= self.QWebEnginePage.FindFlag.FindBackward

        self.web_view.page().findText(text, options)