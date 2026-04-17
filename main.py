"""
amdtr — Another Markdown Editor.
"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent

    return base_path / relative_path

__version__ = "1.2.0"

def main() -> None:
    # Essential for lazy WebEngine loading
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # High-DPI-Scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("amdtr")
    app.setOrganizationName("amdtr")

    # Set icon
    icon_path = resource_path("amdtr-icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    # Fusion Style
    app.setStyle("Fusion")

    from ui.main_window import MainWindow
    # Pass command line arguments (files to open)
    initial_files = sys.argv[1:]
    window = MainWindow(version=__version__, initial_files=initial_files)
    
    # Close native PyInstaller splash if present just before showing window
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
