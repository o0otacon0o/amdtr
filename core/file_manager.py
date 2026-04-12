"""
FileManager — zentrale Datei I/O Operations.

Kapselt alle Dateisystem-Interaktionen:
- Datei-Laden und -Speichern
- Encoding-Detection
- Backup-Erstellung
- Fehler-Handling
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import chardet


class FileManager:
    """
    Zentrale Klasse für alle Datei-Operationen.
    
    Verwaltet Encoding-Detection, Backup-Erstellung und 
    konsistente Fehler-Behandlung.
    """
    
    @staticmethod
    def read_text_file(path: Path) -> tuple[str, bool]:
        """
        Liest eine Textdatei mit automatischer Encoding-Detection.
        
        Returns:
            (text_content, success)
        """
        try:
            # Erst UTF-8 versuchen (Standard für Markdown)
            content = path.read_text(encoding="utf-8")
            return content, True
        except UnicodeDecodeError:
            # Falls UTF-8 fehlschlägt, Encoding detectieren
            try:
                raw_bytes = path.read_bytes()
                detected = chardet.detect(raw_bytes)
                encoding = detected.get('encoding', 'utf-8')
                
                if encoding and encoding.lower() != 'utf-8':
                    content = raw_bytes.decode(encoding)
                    return content, True
                else:
                    # Fallback: als Latin-1 lesen (kann nie fehlschlagen)
                    content = raw_bytes.decode('latin-1')
                    return content, True
                    
            except Exception:
                return "", False
        except (FileNotFoundError, OSError):
            return "", False
    
    @staticmethod
    def write_text_file(path: Path, content: str, create_backup: bool = True) -> bool:
        """
        Schreibt Textinhalt in eine Datei.
        
        Args:
            path: Ziel-Pfad
            content: Text-Inhalt
            create_backup: Backup der existierenden Datei erstellen
            
        Returns:
            True wenn erfolgreich
        """
        try:
            # Verzeichnis erstellen falls nötig
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup erstellen wenn Datei existiert
            if create_backup and path.exists():
                backup_path = FileManager._get_backup_path(path)
                path.rename(backup_path)
            
            # Datei schreiben (immer UTF-8 für neue Dateien)
            path.write_text(content, encoding="utf-8")
            return True
            
        except OSError:
            return False
    
    @staticmethod
    def _get_backup_path(original_path: Path) -> Path:
        """
        Erstellt einen Backup-Pfad: file.md -> file.md.backup
        """
        counter = 1
        backup_path = original_path.with_suffix(original_path.suffix + '.backup')
        
        # Falls .backup schon existiert, .backup.1, .backup.2, ... probieren
        while backup_path.exists():
            backup_path = original_path.with_suffix(
                f"{original_path.suffix}.backup.{counter}"
            )
            counter += 1
            
        return backup_path
    
    @staticmethod
    def safe_file_name(name: str) -> str:
        """
        Macht einen String zu einem sicheren Dateinamen.
        Entfernt/ersetzt problematische Zeichen.
        """
        # Windows-inkompatible Zeichen entfernen
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
            
        # Führende/nachfolgende Leerzeichen und Punkte entfernen  
        name = name.strip(' .')
        
        # Leer oder zu lang -> Default
        if not name or len(name) > 100:
            name = "untitled"
            
        return name
    
    @staticmethod
    def get_relative_path(file_path: Path, workspace_root: Path) -> Optional[Path]:
        """
        Berechnet relativen Pfad einer Datei zum Workspace.
        Gibt None zurück wenn Datei außerhalb des Workspace liegt.
        """
        try:
            return file_path.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return None
            
    @staticmethod
    def find_available_path(preferred_path: Path) -> Path:
        """
        Findet einen verfügbaren Pfad wenn der gewünschte schon existiert.
        Hängt (1), (2), ... an den Dateinamen.
        """
        if not preferred_path.exists():
            return preferred_path
            
        stem = preferred_path.stem
        suffix = preferred_path.suffix
        parent = preferred_path.parent
        
        counter = 1
        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1