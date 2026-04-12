"""
PreviewBridge — QWebChannel-basierte Kommunikation zwischen Python und JS.

Verwaltet:
- Markdown → HTML Übertragung
- Scroll-Synchronisation 
- Debounced Updates (150ms)
- Theme-Injection
"""

from __future__ import annotations
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel


class PreviewBridge(QObject):
    """
    Bridge zwischen Python (Editor) und JavaScript (Preview).
    
    Verwendet QWebChannel für bidirektionale Kommunikation.
    """
    
    # Signals für JavaScript → Python
    scroll_to_line_requested = pyqtSignal(int)
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        
        # Debounce-Timer für Markdown-Updates
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._send_pending_markdown)
        
        # Aktueller Zustand
        self._pending_markdown = ""
        self._current_line = 0
        self._scroll_lock = False
        
    @pyqtSlot(str)
    def update_markdown(self, markdown: str) -> None:
        """
        Aktualisiert Markdown-Inhalt mit Debouncing.
        Wird vom Editor aufgerufen bei Text-Änderungen.
        """
        self._pending_markdown = markdown
        self._update_timer.start(150)  # 150ms Debounce
        
    @pyqtSlot(int)
    def scroll_to_line(self, line: int) -> None:
        """
        Scrollt Preview zur angegebenen Zeile.
        Wird vom Editor aufgerufen bei Cursor-Bewegung.
        """
        if self._scroll_lock:
            return
            
        self._current_line = line
        if hasattr(self, '_web_page') and self._web_page:
            print(f"[DEBUG] Scrolling to line: {line}")
            js_code = f"""
            (function() {{
                if (typeof window.scrollToLine === 'function') {{
                    console.log('Scrolling to line:', {line});
                    window.scrollToLine({line});
                }} else {{
                    console.log('scrollToLine function not available');
                }}
            }})();
            """
            self._execute_javascript(js_code)
        
    @pyqtSlot(int)
    def on_preview_scroll(self, line: int) -> None:
        """
        JavaScript → Python: Preview wurde gescrollt.
        Synchronisiert Editor-Viewport.
        """
        self._scroll_lock = True
        self.scroll_to_line_requested.emit(line)
        
        # Lock nach kurzer Verzögerung wieder aufheben
        QTimer.singleShot(100, lambda: setattr(self, '_scroll_lock', False))
        
    @pyqtSlot(dict)
    def set_theme_vars(self, vars_dict: dict) -> None:
        """
        Injiziert Theme-CSS-Variablen in die Preview.
        """
        if hasattr(self, '_web_page') and self._web_page:
            import json
            vars_json = json.dumps(vars_dict)
            js_code = f"if (window.updateTheme) window.updateTheme({vars_json});"
            self._execute_javascript(js_code)
        
    def _send_pending_markdown(self) -> None:
        """
        Sendet gepufferten Markdown-Inhalt an JavaScript.
        Wird vom Debounce-Timer aufgerufen.
        """
        if not self._pending_markdown:
            print(f"[DEBUG] No pending markdown to send")
            return
            
        if not hasattr(self, '_web_page') or not self._web_page:
            print(f"[DEBUG] No web page available")
            return
            
        print(f"[DEBUG] Sending markdown: {len(self._pending_markdown)} chars")
        
        # JSON-basierte sichere Übertragung
        import json
        markdown_json = json.dumps(self._pending_markdown)
        
        js_code = f"""
        (function() {{
            if (typeof window.updateMarkdown === 'function') {{
                console.log('Calling updateMarkdown with', {len(self._pending_markdown)}, 'chars');
                window.updateMarkdown({markdown_json});
            }} else {{
                console.error('updateMarkdown function not available');
                setTimeout(function() {{
                    if (typeof window.updateMarkdown === 'function') {{
                        console.log('Retry: Calling updateMarkdown');
                        window.updateMarkdown({markdown_json});
                    }} else {{
                        console.error('updateMarkdown still not available after retry');
                    }}
                }}, 200);
            }}
        }})();
        """
        
        self._execute_javascript(js_code)
        
    def set_web_page(self, page) -> None:
        """
        Setzt WebEngine-Page für JavaScript-Aufrufe.
        Wird von PreviewPanel aufgerufen.
        """
        self._web_page = page
        
    def _execute_javascript(self, js_code: str) -> None:
        """
        Führt JavaScript-Code in der WebView aus.
        """
        if hasattr(self, '_web_page') and self._web_page:
            self._web_page.runJavaScript(js_code)
            
            
    def get_web_channel(self) -> QWebChannel:
        """
        Erstellt QWebChannel mit diesem Bridge-Objekt.
        Wird vom PreviewPanel verwendet.
        """
        channel = QWebChannel()
        channel.registerObject("bridge", self)
        return channel