"""Per-artery colors, candidate tint, and the toolbar icon factory."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

# Per-artery overlay colors (pt-BR keys). Alpha keeps the underlying CT
# visible through the overlay; the same RGB is reused at full opacity for
# the toolbar icons.
ARTERY_RGB: dict[str, tuple[int, int, int]] = {
    "TCE": (50, 120, 255),   # azul   (tronco da coronária esquerda)
    "DA":  (230, 30, 30),    # vermelho (descendente anterior)
    "Cx":  (240, 220, 30),   # amarelo (circunflexa)
    "CD":  (250, 140, 30),   # laranja (coronária direita)
    "DP":  (40, 200, 60),    # verde  (descendente posterior)
}

ARTERY_COLORS: dict[str, QColor] = {
    artery: QColor(r, g, b, 150) for artery, (r, g, b) in ARTERY_RGB.items()
}

# Tint applied to pixels >=130 HU that are not yet part of any ROI. Pink is
# distinct from every artery color above (blue/red/yellow/orange/green).
CANDIDATE_COLOR: QColor = QColor(255, 90, 200, 130)


def artery_color(artery: str) -> QColor:
    return ARTERY_COLORS.get(artery, QColor(255, 255, 255, 140))


def eye_open_icon(size: int = 32) -> QIcon:
    """A simple monochrome 'eye open' icon for overlay-visibility toggles."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Almond-shaped outline approximated with an ellipse.
        pen = QPen(QColor(230, 230, 230), 1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        almond_w = size * 0.78
        almond_h = size * 0.42
        painter.drawEllipse(
            (size - almond_w) / 2,
            (size - almond_h) / 2,
            almond_w,
            almond_h,
        )
        # Iris + pupil.
        painter.setBrush(QColor(80, 140, 220))
        painter.setPen(QPen(QColor(40, 80, 140), 1.0))
        iris = size * 0.28
        painter.drawEllipse(
            (size - iris) / 2,
            (size - iris) / 2,
            iris,
            iris,
        )
        painter.setBrush(QColor(20, 20, 20))
        painter.setPen(Qt.PenStyle.NoPen)
        pupil = size * 0.12
        painter.drawEllipse(
            (size - pupil) / 2,
            (size - pupil) / 2,
            pupil,
            pupil,
        )
    finally:
        painter.end()
    return QIcon(pix)


def eye_closed_icon(size: int = 32) -> QIcon:
    """A simple monochrome 'eye closed' icon (closed eyelid + lashes)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(220, 220, 220), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Closed-eyelid curve (a shallow arc).
        margin = size * 0.12
        rect_x = margin
        rect_y = size * 0.30
        rect_w = size - 2 * margin
        rect_h = size * 0.40
        painter.drawArc(int(rect_x), int(rect_y), int(rect_w), int(rect_h), 0 * 16, 180 * 16)
        # Three short eyelashes hanging down from the arc.
        cy = rect_y + rect_h / 2
        for dx, dy in [(-0.30, 0.18), (0.0, 0.22), (0.30, 0.18)]:
            x0 = size / 2 + dx * size
            y0 = cy + 2
            painter.drawLine(int(x0), int(y0), int(x0 + dy * size * 0.4), int(y0 + dy * size * 1.0))
    finally:
        painter.end()
    return QIcon(pix)


def eraser_icon(size: int = 32) -> QIcon:
    """A small pink-block eraser icon for the toolbar."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(size / 2, size / 2)
        painter.rotate(-25)
        # Eraser body (pink)
        painter.setBrush(QColor(255, 170, 175))
        painter.setPen(QPen(QColor(30, 30, 30), 1.2))
        body_w, body_h = size * 0.72, size * 0.34
        painter.drawRoundedRect(-body_w / 2, -body_h / 2, body_w, body_h, 3, 3)
        # Metal band on the left side (the classic two-tone pencil eraser look)
        painter.setBrush(QColor(180, 180, 180))
        band_w = size * 0.14
        painter.drawRect(-body_w / 2 + body_w * 0.05, -body_h / 2, band_w, body_h)
    finally:
        painter.end()
    return QIcon(pix)


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
