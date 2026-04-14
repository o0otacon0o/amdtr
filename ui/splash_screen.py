"""
SplashScreen — a loading screen for the application.
"""

from PyQt6.QtWidgets import QSplashScreen, QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen


class SplashScreen(QSplashScreen):

    def __init__(self, logo_path: str) -> None:
        pixmap = QPixmap(logo_path).scaled(
            640, 480, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        super().__init__(pixmap)

        # Allow drawing on the splash screen
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self._progress = 0
        self._message = "Initializing..."

    def set_progress(self, value: int, message: str = "") -> None:
        """Updates the progress and message."""
        self._progress = value
        if message:
            self._message = message
        self.showMessage(
            self._message, 
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
            QColor("white")
        )
        # Force update and process events to keep the UI responsive
        from PyQt6.QtWidgets import QApplication
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter) -> None:
        """Custom drawing for the splash screen."""
        super().drawContents(painter)

        # Draw a spinning circle (loading indicator)
        # We can use the current time to rotate it
        import time
        angle = (time.time() * 360) % 360

        rect = self.rect()
        loader_size = 50
        loader_rect = QRect(
            rect.width() // 2 - loader_size // 2,
            rect.height() - 120,
            loader_size,
            loader_size
        )

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background of the circle
        pen = QPen(QColor(255, 255, 255, 30))
        pen.setWidth(6)
        painter.setPen(pen)
        painter.drawEllipse(loader_rect)

        # Foreground of the circle (the "spinner")
        # Use a nice highlight color
        pen.setColor(QColor("#569CD6")) # Visual Studio Code like Blue
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # We use a slightly different math for smoother movement
        # 16 is fixed-point for degrees
        start_angle = int(-angle * 16)
        span_angle = 120 * 16
        painter.drawArc(loader_rect, start_angle, span_angle)
