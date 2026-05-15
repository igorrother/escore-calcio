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


def _draw_eye_outline(painter: QPainter, size: int) -> tuple[float, float]:
    """Draw the eye almond + return (iris_size, iris_origin) for caller."""
    pen = QPen(QColor(230, 230, 230), 1.6)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    almond_w = size * 0.86
    almond_h = size * 0.46
    painter.drawEllipse(
        (size - almond_w) / 2,
        (size - almond_h) / 2,
        almond_w,
        almond_h,
    )
    iris = size * 0.36
    iris_origin = (size - iris) / 2
    return iris, iris_origin


def _draw_pupil(painter: QPainter, size: int) -> None:
    """Center pupil dot, drawn last so it sits over the iris."""
    painter.setBrush(QColor(20, 20, 20))
    painter.setPen(Qt.PenStyle.NoPen)
    pupil = size * 0.14
    painter.drawEllipse(
        (size - pupil) / 2,
        (size - pupil) / 2,
        pupil,
        pupil,
    )


def overlay_all_eye_icon(size: int = 32) -> QIcon:
    """Eye icon with a 4-quadrant artery-colored iris.

    Used for the toolbar toggle that controls visibility of ALL overlays.
    The four quadrants pick the four most-distinct artery colors so the
    icon reads as "shows all the colored overlays".
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        iris, origin = _draw_eye_outline(painter, size)
        # Pie slices in 4 representative artery colors.
        # Qt drawPie angles are in 1/16 degrees, 0° = 3 o'clock, CCW.
        quadrant_colors = [
            QColor(*ARTERY_RGB["DA"]),    # top-right    (red)
            QColor(*ARTERY_RGB["TCE"]),   # top-left     (blue)
            QColor(*ARTERY_RGB["DP"]),    # bottom-left  (green)
            QColor(*ARTERY_RGB["Cx"]),    # bottom-right (yellow)
        ]
        painter.setPen(QPen(QColor(40, 40, 40), 0.7))
        for i, color in enumerate(quadrant_colors):
            painter.setBrush(color)
            painter.drawPie(
                int(origin), int(origin), int(iris), int(iris),
                int(i * 90 * 16), int(90 * 16),
            )
        _draw_pupil(painter, size)
    finally:
        painter.end()
    return QIcon(pix)


def overlay_candidate_eye_icon(size: int = 32) -> QIcon:
    """Eye icon with a solid pink iris — matches CANDIDATE_COLOR.

    Used for the toolbar toggle that controls visibility of ONLY the
    candidate (pink) overlay.
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        iris, origin = _draw_eye_outline(painter, size)
        # Solid pink iris — same color as the candidate overlay tint
        # (opaque here so the icon reads clearly at 32 px).
        candidate_solid = QColor(
            CANDIDATE_COLOR.red(),
            CANDIDATE_COLOR.green(),
            CANDIDATE_COLOR.blue(),
            255,
        )
        painter.setBrush(candidate_solid)
        painter.setPen(QPen(QColor(40, 40, 40), 0.7))
        painter.drawEllipse(int(origin), int(origin), int(iris), int(iris))
        _draw_pupil(painter, size)
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
