"""Right-side panel with patient header, per-artery totals, grand total, risk class."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..scoring import ARTERIES, Lesion, grand_total, risk_category, totals_by_artery
from ..series_model import Series
from .roi_tools import artery_color

_RISK_COLORS = {
    "none": QColor(120, 200, 120),
    "minimal": QColor(120, 170, 220),
    "mild": QColor(230, 220, 100),
    "moderate": QColor(230, 160, 80),
    "severe": QColor(220, 80, 80),
}


class ScoreTable(QWidget):
    """Live-updated panel summarizing Agatston results."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(300)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Patient header
        self._patient_lbl = QLabel("No study loaded")
        self._patient_lbl.setWordWrap(True)
        bold = QFont()
        bold.setBold(True)
        self._patient_lbl.setFont(bold)
        root.addWidget(self._patient_lbl)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep1)

        # Per-artery totals
        title = QLabel("Per-artery Agatston score")
        title.setFont(bold)
        root.addWidget(title)

        self._artery_value_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        for row, artery in enumerate(ARTERIES):
            color_box = QLabel("    ")
            color_box.setAutoFillBackground(True)
            pal = color_box.palette()
            pal.setColor(QPalette.ColorRole.Window, artery_color(artery))
            color_box.setPalette(pal)
            color_box.setFixedWidth(18)
            color_box.setFixedHeight(14)

            name = QLabel(artery)
            value = QLabel("0.0")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._artery_value_labels[artery] = value

            grid.addWidget(color_box, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(value, row, 2)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep2)

        # Grand total + risk
        total_title = QLabel("Total Agatston score")
        total_title.setFont(bold)
        root.addWidget(total_title)

        self._total_lbl = QLabel("0.0")
        big = QFont()
        big.setPointSize(22)
        big.setBold(True)
        self._total_lbl.setFont(big)
        self._total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._total_lbl)

        self._risk_lbl = QLabel("Risk: —")
        self._risk_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._risk_lbl.setAutoFillBackground(True)
        risk_font = QFont()
        risk_font.setBold(True)
        risk_font.setPointSize(12)
        self._risk_lbl.setFont(risk_font)
        self._risk_lbl.setMinimumHeight(30)
        root.addWidget(self._risk_lbl)

        root.addStretch(1)

        self._lesions: list[Lesion] = []

    def set_series_info(self, series: Series | None) -> None:
        if series is None:
            self._patient_lbl.setText("No study loaded")
            return
        text = (
            f"Patient: {series.patient_name or '(unknown)'}\n"
            f"ID: {series.patient_id or '—'}\n"
            f"Study date: {series.study_date or '—'}\n"
            f"Series: {series.series_description or '(no description)'} "
            f"({series.num_slices} slices, "
            f"{series.slice_thickness:g} mm)"
            if series.slice_thickness is not None
            else f"Series: {series.series_description or '(no description)'} ({series.num_slices} slices)"
        )
        self._patient_lbl.setText(text)

    def set_lesions(self, lesions: list[Lesion]) -> None:
        self._lesions = list(lesions)
        self._refresh()

    def add_lesion(self, les: Lesion) -> None:
        self._lesions.append(les)
        self._refresh()

    def clear_lesions(self) -> None:
        self._lesions = []
        self._refresh()

    def _refresh(self) -> None:
        per = totals_by_artery(self._lesions)
        for artery, value in per.items():
            self._artery_value_labels[artery].setText(f"{value:.1f}")
        total = grand_total(self._lesions)
        self._total_lbl.setText(f"{total:.1f}")
        risk = risk_category(total)
        self._risk_lbl.setText(f"Risk: {risk}")
        pal = self._risk_lbl.palette()
        pal.setColor(QPalette.ColorRole.Window, _RISK_COLORS.get(risk, QColor(180, 180, 180)))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        self._risk_lbl.setPalette(pal)
