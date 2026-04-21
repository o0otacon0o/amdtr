"""
amdtr — Another Markdown Editor.
"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent

    return base_path / relative_path

__version__ = "1.2.0"
APP_ID = "amdtr_instance_unique_id"

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

    # Single Instance Check
    socket = QLocalSocket()
    socket.connectToServer(APP_ID)
    if socket.waitForConnected(500):
        # Another instance is already running
        # Send arguments to it
        args = "|".join(sys.argv[1:])
        socket.write(args.encode('utf-8'))
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        sys.exit(0)

    # If we are here, we are the first instance
    server = QLocalServer()
    # Cleanup in case of previous crash
    QLocalServer.removeServer(APP_ID)
    if not server.listen(APP_ID):
        # This can happen if another process is using the same name
        # but is not a QLocalServer or is locked
        pass

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

    def on_new_connection():
        client_socket = server.nextPendingConnection()
        if client_socket.waitForReadyRead(500):
            data = client_socket.readAll().data().decode('utf-8')
            if data:
                files = data.split('|')
                # Filter out empty strings from join
                files = [f for f in files if f]
                if files:
                    window._handle_initial_files(files)
            
            # Bring to front
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            window.raise_()
            window.activateWindow()
        client_socket.disconnectFromServer()

    server.newConnection.connect(on_new_connection)
    
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
