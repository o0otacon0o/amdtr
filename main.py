"""
amdtr — Another Markdown Editor.
"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent

    return base_path / relative_path

__version__ = "1.0.0"

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

    from ui.splash_screen import SplashScreen
    logo_path = resource_path("amdtr-logo.png")
    splash = SplashScreen(str(logo_path))
    splash.show()
    
    # Animate the splash screen
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(splash.repaint)
    timer.start(16) # ~60 FPS

    app.processEvents()

    window = MainWindow(version=__version__, splash=splash)
    
    # Let MainWindow do its thing, then hide splash
    window.show()
    splash.finish(window)
    timer.stop()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
