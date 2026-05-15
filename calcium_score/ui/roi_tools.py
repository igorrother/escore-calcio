"""Per-artery colors and constants shared by the ROI tools and viewer."""

from __future__ import annotations

from PySide6.QtGui import QColor

# Distinct, high-contrast colors for each coronary artery's overlay.
ARTERY_COLORS: dict[str, QColor] = {
    "LM": QColor(255, 0, 255, 140),     # magenta
    "LAD": QColor(255, 0, 0, 140),      # red
    "LCx": QColor(255, 165, 0, 140),    # orange
    "RCA": QColor(0, 200, 255, 140),    # cyan
    "PDA": QColor(0, 255, 0, 140),      # green
}

# Tint applied to pixels >=130 HU that are not yet part of any ROI, so the
# user can see candidate calcium at a glance. Yellow is intentionally distinct
# from every artery color above.
CANDIDATE_COLOR: QColor = QColor(255, 255, 0, 110)


def artery_color(artery: str) -> QColor:
    return ARTERY_COLORS.get(artery, QColor(255, 255, 0, 140))
