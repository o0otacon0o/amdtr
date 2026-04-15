"""
PreviewBridge — QWebChannel-based communication between Python and JS.

Manages:
- Markdown → HTML transfer
- Scroll synchronization 
- Debounced updates (150ms)
- Theme injection
"""

from __future__ import annotations
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel


class PreviewBridge(QObject):
    """
    Bridge between Python (editor) and JavaScript (preview).
    
    Uses QWebChannel for bidirectional communication.
    """
    
    # Signals for JavaScript → Python
    scroll_to_line_requested = pyqtSignal(int)
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        
        # Debounce timer for Markdown updates
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._send_pending_markdown)
        
        # Current state
        self._pending_markdown = ""
        self._current_line = 0
        self._scroll_lock = False
        
    @pyqtSlot(str)
    def update_markdown(self, markdown: str) -> None:
        """
        Updates Markdown content with debouncing.
        Called by the editor on text changes.
        """
        self._pending_markdown = markdown
        self._update_timer.start(150)  # 150ms Debounce
        
    @pyqtSlot(int)
    def scroll_to_line(self, line: int) -> None:
        """
        Scrolls preview to the specified line.
        Called by the editor on cursor movement.
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
        JavaScript → Python: Preview was scrolled.
        Synchronizes editor viewport.
        """
        self._scroll_lock = True
        self.scroll_to_line_requested.emit(line)
        
        # Release lock after a short delay
        QTimer.singleShot(100, lambda: setattr(self, '_scroll_lock', False))
        
    @pyqtSlot(dict)
    def set_theme_vars(self, vars_dict: dict) -> None:
        """
        Injects theme CSS variables into the preview.
        """
        if hasattr(self, '_web_page') and self._web_page:
            import json
            vars_json = json.dumps(vars_dict)
            js_code = f"if (window.updateTheme) window.updateTheme({vars_json});"
            self._execute_javascript(js_code)

    @pyqtSlot(str)
    def set_base_path(self, path: str) -> None:
        """
        Sets the base path for relative resource resolution in the preview.
        """
        if hasattr(self, '_web_page') and self._web_page:
            # Ensure path uses forward slashes for JS compatibility
            path = path.replace("\\", "/")
            js_code = f"if (window.updateBasePath) window.updateBasePath('{path}');"
            self._execute_javascript(js_code)
        
    @pyqtSlot(str, str)
    def save_image(self, data_url: str, suggested_name: str) -> None:
        """
        JavaScript → Python: Save an image from a Data URL.
        Opens a file dialog and saves the image.
        """
        import base64
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path

        try:
            # Extract base64 data
            if not data_url.startswith("data:image/"):
                print(f"[ERROR] Invalid data URL: {data_url[:50]}...")
                return

            header, encoded = data_url.split(",", 1)
            file_ext = header.split(";")[0].split("/")[1]
            if file_ext == "svg+xml":
                file_ext = "svg"
            
            image_data = base64.b64decode(encoded)

            # Open file dialog
            file_path, _ = QFileDialog.getSaveFileName(
                None,
                "Save Image",
                suggested_name if suggested_name.endswith(f".{file_ext}") else f"{suggested_name}.{file_ext}",
                f"Images (*.{file_ext});;All Files (*)"
            )

            if file_path:
                Path(file_path).write_bytes(image_data)
                print(f"[INFO] Image saved to: {file_path}")

        except Exception as e:
            print(f"[ERROR] Failed to save image: {e}")

    @pyqtSlot(str)
    def copy_to_clipboard(self, text: str) -> None:
        """
        JavaScript → Python: Copy text to clipboard.
        Normalizes line endings for Windows if necessary.
        """
        import sys
        if sys.platform == "win32":
            # Ensure CRLF line endings on Windows for better compatibility
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")

        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        print("[INFO] Text copied to clipboard (normalized line endings)")

    @pyqtSlot(str)
    def copy_image_to_clipboard(self, data_url: str) -> None:
        """
        JavaScript → Python: Copy an image from a Data URL to clipboard.
        """
        import base64
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QImage, QPixmap

        try:
            if not data_url.startswith("data:image/"):
                return

            header, encoded = data_url.split(",", 1)
            image_data = base64.b64decode(encoded)
            
            image = QImage.fromData(image_data)
            if not image.isNull():
                clipboard = QApplication.clipboard()
                clipboard.setImage(image)
                print("[INFO] Image copied to clipboard")
        except Exception as e:
            print(f"[ERROR] Failed to copy image to clipboard: {e}")

    def _send_pending_markdown(self) -> None:
        """
        Sends buffered Markdown content to JavaScript.
        Called by the debounce timer.
        """
        if not self._pending_markdown:
            print(f"[DEBUG] No pending markdown to send")
            return
            
        if not hasattr(self, '_web_page') or not self._web_page:
            print(f"[DEBUG] No web page available")
            return
            
        print(f"[DEBUG] Sending markdown: {len(self._pending_markdown)} chars")
        
        # JSON-based secure transfer
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
        Sets WebEngine page for JavaScript calls.
        Called by PreviewPanel.
        """
        self._web_page = page
        
    def _execute_javascript(self, js_code: str) -> None:
        """
        Executes JavaScript code in the WebView.
        """
        if hasattr(self, '_web_page') and self._web_page:
            self._web_page.runJavaScript(js_code)
            
            
    def get_web_channel(self) -> QWebChannel:
        """
        Creates QWebChannel with this bridge object.
        Used by PreviewPanel.
        """
        channel = QWebChannel()
        channel.registerObject("bridge", self)
        return channel
