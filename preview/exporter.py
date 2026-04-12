"""
Exporter — Generiert Standalone-HTML Dateien aus Markdown.
"""

from __future__ import annotations
from pathlib import Path
import re

import json

class HTMLExporter:
    """
    Exportiert Markdown-Inhalt in eine eigenständige HTML-Datei.
    Bettet alle notwendigen JS/CSS-Bibliotheken ein.
    """
    
    CDN_FALLBACKS = {
        "marked.min.js": "https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js",
        "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11.0.0/dist/mermaid.min.js",
        "katex.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.js",
        "auto-render.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/contrib/auto-render.min.js",
        "highlight.min.js": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js",
        "katex.min.css": "https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.css",
        "github.min.css": "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css"
    }

    def __init__(self, template_path: Path | None = None) -> None:
        self._resources_dir = Path(__file__).parent.parent / "resources"
        self._vendor_dir = self._resources_dir / "vendor"
        self._template_path = template_path or (self._resources_dir / "preview.html")
        
    def export(self, markdown: str, output_path: Path, title: str = "Exported Note") -> bool:
        try:
            if not self._template_path.exists():
                return False
                
            template = self._template_path.read_text(encoding="utf-8")
            html = self._prepare_standalone_html(template, markdown, title)
            
            output_path.write_text(html, encoding="utf-8")
            return True
            
        except Exception as e:
            print(f"[ERROR] Export failed: {e}")
            return False
            
    def _prepare_standalone_html(self, template: str, markdown: str, title: str) -> str:
        """Erzeugt ein vollständig autonomes HTML-Dokument."""
        
        # 1. Titel setzen
        html = template.replace("<title>amdtr Preview</title>", f"<title>{title}</title>")
        
        # 2. QWebChannel entfernen
        html = html.replace('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>', '')
        
        # 3. Assets einbetten (CSS)
        html = self._embed_css(html)
        
        # 4. Assets einbetten (JS)
        html = self._embed_js(html)
        
        # 5. Markdown injizieren (Sicher via JSON)
        md_json = json.dumps(markdown)
        injection_script = f"""
    <script>
        document.addEventListener('DOMContentLoaded', async () => {{
            try {{
                // Theme initialisieren (Export ist standardmäßig hell)
                if (window.updateTheme) {{
                    window.updateTheme({{
                        '--syntax': 'light',
                        '--mermaid': 'default'
                    }});
                }}
                
                const md = {md_json};
                if (window.updateMarkdown) {{
                    await window.updateMarkdown(md);
                }}
            }} catch (e) {{
                console.error("Rendering failed:", e);
            }}
        }});
    </script>
        """
        
        # WICHTIG: Nur das LETZTE </body> ersetzen, um nicht in eingebettetes JS zu grätschen
        if "</body>" in html:
            parts = html.rpartition("</body>")
            html = parts[0] + injection_script + "</body>" + parts[2]
        else:
            html += injection_script
            
        return html

    def _embed_css(self, html: str) -> str:
        """Ersetzt <link> durch <style> Inhalte (außer KaTeX)."""
        def replace_link(match):
            href = match.group(1)
            filename = href.split('/')[-1]
            
            # KaTeX wegen Fonts besser via CDN
            if "katex" in filename:
                return f'<link rel="stylesheet" href="{self.CDN_FALLBACKS["katex.min.css"]}">'
                
            local_path = self._vendor_dir / filename
            if local_path.exists():
                content = local_path.read_text(encoding="utf-8")
                return f"<style>/* {filename} */\n{content}\n</style>"
            
            cdn_url = self.CDN_FALLBACKS.get(filename, href)
            return f'<link rel="stylesheet" href="{cdn_url}">'

        return re.sub(r'<link.*?href="(vendor/.*?)".*?>', replace_link, html)

    def _embed_js(self, html: str) -> str:
        """Ersetzt <script src> durch <script> Inhalte."""
        def replace_script(match):
            src = match.group(1)
            filename = src.split('/')[-1]
            local_path = self._vendor_dir / filename
            
            if local_path.exists():
                content = local_path.read_text(encoding="utf-8")
                # KRITISCH: </script> innerhalb von JS maskieren
                content = content.replace("</script>", "<\\/script>")
                return f"<script>/* {filename} */\n{content}\n</script>"
            
            cdn_url = self.CDN_FALLBACKS.get(filename, src)
            return f'<script src="{cdn_url}"></script>'

        return re.sub(r'<script src="(vendor/.*?)"></script>', replace_script, html)
