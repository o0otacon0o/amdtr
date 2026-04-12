"""
Exporter — Generates standalone HTML files from Markdown.
"""

from __future__ import annotations
from pathlib import Path
import re

import json

class HTMLExporter:
    """
    Exports Markdown content to a standalone HTML file.
    Embeds all necessary JS/CSS libraries.
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
        
    def export(self, markdown: str, output_path: Path, title: str = "Exported Note", base_path: Path | None = None) -> bool:
        try:
            if not self._template_path.exists():
                return False
                
            # 0. Embed images in Markdown
            markdown = self._embed_images(markdown, base_path)
            
            template = self._template_path.read_text(encoding="utf-8")
            html = self._prepare_standalone_html(template, markdown, title)
            
            output_path.write_text(html, encoding="utf-8")
            return True
            
        except Exception as e:
            print(f"[ERROR] Export failed: {e}")
            return False

    def _embed_images(self, markdown: str, base_path: Path | None) -> str:
        """
        Finds all image references in Markdown and converts local images to Base64.
        """
        import base64
        import mimetypes

        def replace_img(match):
            alt_text = match.group(1)
            img_path_str = match.group(2)
            
            # Skip URLs, data URIs, or absolute paths (unless they exist)
            if img_path_str.startswith(("http://", "https://", "data:")):
                return match.group(0)
            
            # Try to resolve path
            img_path = Path(img_path_str)
            if not img_path.is_absolute() and base_path:
                img_path = base_path / img_path
                
            if img_path.exists() and img_path.is_file():
                try:
                    mime_type, _ = mimetypes.guess_type(img_path)
                    if not mime_type:
                        mime_type = "image/png" # Fallback
                        
                    with open(img_path, "rb") as f:
                        encoded_string = base64.b64encode(f.read()).decode("utf-8")
                        return f"![{alt_text}](data:{mime_type};base64,{encoded_string})"
                except Exception as e:
                    print(f"[WARNING] Could not embed image {img_path}: {e}")
            
            return match.group(0)

        # Regex for Markdown images: ![alt](path)
        markdown = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_img, markdown)

        # Regex for Wikilink images: ![[path]] or ![[path|alt]]
        def replace_wikilink_img(match):
            parts = match.group(1).split('|')
            img_path_str = parts[0].strip()
            alt_text = parts[1].strip() if len(parts) > 1 else ""
            
            # Try to resolve path (simplified, as we don't have the full WikilinkResolver here)
            img_path = Path(img_path_str)
            if not img_path.is_absolute() and base_path:
                # Check directly in base_path first
                test_path = base_path / img_path
                if test_path.exists():
                    img_path = test_path
            
            if img_path.exists() and img_path.is_file():
                try:
                    mime_type, _ = mimetypes.guess_type(img_path)
                    if not mime_type: mime_type = "image/png"
                    with open(img_path, "rb") as f:
                        encoded_string = base64.b64encode(f.read()).decode("utf-8")
                        # Convert to standard Markdown image with Base64
                        return f"![{alt_text}](data:{mime_type};base64,{encoded_string})"
                except Exception:
                    pass
            
            return match.group(0)

        return re.sub(r'!\[\[(.*?)\]\]', replace_wikilink_img, markdown)
            
    def _prepare_standalone_html(self, template: str, markdown: str, title: str) -> str:
        """Creates a fully autonomous HTML document."""
        
        # 1. Set title
        html = template.replace("<title>amdtr Preview</title>", f"<title>{title}</title>")
        
        # 2. Remove QWebChannel
        html = html.replace('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>', '')
        
        # 3. Embed assets (CSS)
        html = self._embed_css(html)
        
        # 4. Embed assets (JS)
        html = self._embed_js(html)
        
        # 5. Inject Markdown (secure via JSON)
        md_json = json.dumps(markdown)
        injection_script = f"""
    <script>
        document.addEventListener('DOMContentLoaded', async () => {{
            try {{
                // Initialize theme (export is light by default)
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
        
        # IMPORTANT: Replace only the LAST </body> to avoid interfering with embedded JS
        if "</body>" in html:
            parts = html.rpartition("</body>")
            html = parts[0] + injection_script + "</body>" + parts[2]
        else:
            html += injection_script
            
        return html

    def _embed_css(self, html: str) -> str:
        """Replaces <link> with <style> content (except KaTeX)."""
        def replace_link(match):
            href = match.group(1)
            filename = href.split('/')[-1]
            
            # KaTeX is better via CDN because of fonts
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
        """Replaces <script src> with <script> content."""
        def replace_script(match):
            src = match.group(1)
            filename = src.split('/')[-1]
            local_path = self._vendor_dir / filename
            
            if local_path.exists():
                content = local_path.read_text(encoding="utf-8")
                # CRITICAL: Mask </script> within JS
                content = content.replace("</script>", "<\\/script>")
                return f"<script>/* {filename} */\n{content}\n</script>"
            
            cdn_url = self.CDN_FALLBACKS.get(filename, src)
            return f'<script src="{cdn_url}"></script>'

        return re.sub(r'<script src="(vendor/.*?)"></script>', replace_script, html)
