"""Per-artery colors, candidate tint, and the toolbar icon factory."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

# Per-artery overlay colors. Alpha keeps the underlying CT visible through
# the overlay; the same RGB is reused at full opacity for the toolbar icons.
ARTERY_RGB: dict[str, tuple[int, int, int]] = {
    "LM":  (50, 120, 255),   # blue
    "LAD": (230, 30, 30),    # red
    "LCx": (240, 220, 30),   # yellow
    "RCA": (250, 140, 30),   # orange
    "PDA": (40, 200, 60),    # green
}

ARTERY_COLORS: dict[str, QColor] = {
    artery: QColor(r, g, b, 150) for artery, (r, g, b) in ARTERY_RGB.items()
}

# Tint applied to pixels >=130 HU that are not yet part of any ROI. Pink is
# distinct from every artery color above (blue/red/yellow/orange/green).
CANDIDATE_COLOR: QColor = QColor(255, 90, 200, 130)


def artery_color(artery: str) -> QColor:
    return ARTERY_COLORS.get(artery, QColor(255, 255, 255, 140))


def artery_icon(artery: str, size: int = 32) -> QIcon:
    """Solid colored circle icon labeled with the artery abbreviation."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r, g, b = ARTERY_RGB.get(artery, (255, 255, 255))
        painter.setBrush(QColor(r, g, b))
        painter.setPen(QPen(QColor(20, 20, 20), 1))
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Pick black or white text based on relative luminance.
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = QColor(0, 0, 0) if luminance > 140 else QColor(255, 255, 255)
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(max(8, size * 9 // 32))
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, artery)
    finally:
        painter.end()
    return QIcon(pix)
