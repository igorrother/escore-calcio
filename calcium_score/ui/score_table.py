"""Right-side panel with patient header, per-artery totals, grand total, risk class."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..mesa_percentile import (
    parse_dicom_age_years,
    percentile_bucket,
)
from ..scoring import ARTERIES, Lesion, grand_total, risk_category, totals_by_artery
from ..series_model import Series
from .roi_tools import artery_color


# UI label -> internal MESA race code. "" means "skip percentile".
RACE_OPTIONS: list[tuple[str, str]] = [
    ("— não informada", ""),
    ("Branca", "white"),
    ("Preta", "black"),
    ("Hispânica", "hispanic"),
    ("Chinesa", "chinese"),
]

_BUCKET_COLORS = {
    "<25": QColor(120, 200, 120),       # verde
    "25-50": QColor(170, 210, 130),     # verde-amarelado
    "50-75": QColor(230, 220, 100),     # amarelo
    "75-90": QColor(230, 160, 80),      # laranja
    ">90": QColor(220, 80, 80),         # vermelho
}


# DICOM AS unit -> pt-BR abbreviation: Y/M/W/D = anos/meses/semanas/dias
_AGE_UNITS = {"Y": "a", "M": "m", "W": "s", "D": "d"}


def format_dicom_date(date: str) -> str:
    """Convert DICOM DA (YYYYMMDD) to DD/MM/YYYY. Pass through anything else."""
    if not date:
        return ""
    if len(date) == 8 and date.isdigit():
        return f"{date[6:8]}/{date[4:6]}/{date[0:4]}"
    return date


def _format_dicom_age(age: str) -> str:
    """Convert DICOM PatientAge (e.g. '045Y') to a friendlier '45 a' (pt-BR).

    DICOM AS format: 3 digits + Y/M/W/D unit. Returns the input unchanged
    if it doesn't match the expected pattern, and "" if input is falsy.
    """
    if not age:
        return ""
    if len(age) < 4:
        return age
    try:
        n = int(age[:3])
    except ValueError:
        return age
    suffix = _AGE_UNITS.get(age[3].upper(), age[3].lower())
    return f"{n} {suffix}"


_RISK_COLORS = {
    "ausente": QColor(120, 200, 120),         # verde
    "mínimo": QColor(140, 200, 220),          # azul claro
    "discreto": QColor(230, 220, 100),        # amarelo
    "moderado": QColor(230, 160, 80),         # laranja
    "acentuado": QColor(220, 80, 80),         # vermelho
    "muito acentuado": QColor(150, 30, 30),   # vermelho escuro
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
        self._patient_lbl = QLabel("Nenhum estudo carregado")
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
        title = QLabel("Escore de Agatston por artéria")
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
        total_title = QLabel("Escore total de Agatston")
        total_title.setFont(bold)
        root.addWidget(total_title)

        self._total_lbl = QLabel("0.0")
        big = QFont()
        big.setPointSize(22)
        big.setBold(True)
        self._total_lbl.setFont(big)
        self._total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._total_lbl)

        self._risk_lbl = QLabel("—")
        self._risk_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._risk_lbl.setAutoFillBackground(True)
        risk_font = QFont()
        risk_font.setBold(True)
        risk_font.setPointSize(12)
        self._risk_lbl.setFont(risk_font)
        self._risk_lbl.setMinimumHeight(30)
        root.addWidget(self._risk_lbl)

        # MESA percentile section
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep3)

        mesa_title = QLabel("Percentil MESA")
        mesa_title.setFont(bold)
        root.addWidget(mesa_title)

        race_row = QHBoxLayout()
        race_row.addWidget(QLabel("Raça/Etnia:"))
        self._race_combo = QComboBox()
        for label, _code in RACE_OPTIONS:
            self._race_combo.addItem(label)
        self._race_combo.currentIndexChanged.connect(lambda _i: self._refresh())
        race_row.addWidget(self._race_combo, stretch=1)
        root.addLayout(race_row)

        self._percentile_lbl = QLabel("—")
        self._percentile_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._percentile_lbl.setAutoFillBackground(True)
        pct_font = QFont()
        pct_font.setBold(True)
        pct_font.setPointSize(12)
        self._percentile_lbl.setFont(pct_font)
        self._percentile_lbl.setMinimumHeight(30)
        self._percentile_lbl.setToolTip(
            "Faixa de percentil MESA (McClelland 2006) para a idade, sexo "
            "e raça/etnia. Requer idade entre 45 e 84 anos."
        )
        root.addWidget(self._percentile_lbl)

        root.addStretch(1)

        self._series: Series | None = None
        self._lesions: list[Lesion] = []

    def set_series_info(self, series: Series | None) -> None:
        self._series = series
        if series is None:
            self._patient_lbl.setText("Nenhum estudo carregado")
            self._refresh()
            return

        demo_bits = []
        if series.patient_sex:
            demo_bits.append(series.patient_sex)
        age = _format_dicom_age(series.patient_age)
        if age:
            demo_bits.append(age)
        demographics = f"  ({', '.join(demo_bits)})" if demo_bits else ""

        if series.slice_thickness is not None:
            series_line = (
                f"Série: {series.series_description or '(sem descrição)'} "
                f"({series.num_slices} fatias, {series.slice_thickness:g} mm)"
            )
        else:
            series_line = (
                f"Série: {series.series_description or '(sem descrição)'} "
                f"({series.num_slices} fatias)"
            )

        text = (
            f"Paciente: {series.patient_name or '(desconhecido)'}{demographics}\n"
            f"ID: {series.patient_id or '—'}\n"
            f"Data do estudo: {format_dicom_date(series.study_date) or '—'}\n"
            f"{series_line}"
        )
        self._patient_lbl.setText(text)
        self._refresh()

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
        self._risk_lbl.setText(f"{risk}")
        pal = self._risk_lbl.palette()
        pal.setColor(QPalette.ColorRole.Window, _RISK_COLORS.get(risk, QColor(180, 180, 180)))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        self._risk_lbl.setPalette(pal)

        self._refresh_percentile(total)

    def _refresh_percentile(self, total: float) -> None:
        race_code = RACE_OPTIONS[self._race_combo.currentIndex()][1]
        bucket: str | None = None
        reason: str = ""
        if not race_code:
            reason = "selecione a raça/etnia"
        elif self._series is None:
            reason = "abra uma série"
        else:
            sex = (self._series.patient_sex or "").upper()
            if sex not in ("M", "F"):
                reason = "sexo ausente no DICOM"
            else:
                age = parse_dicom_age_years(self._series.patient_age)
                if age is None:
                    reason = "idade ausente no DICOM"
                elif age < 45 or age > 84:
                    reason = "idade fora de 45–84 (MESA)"
                else:
                    bucket = percentile_bucket(total, age, sex, race_code)

        pal = self._percentile_lbl.palette()
        if bucket is None:
            self._percentile_lbl.setText(f"— ({reason})" if reason else "—")
            pal.setColor(QPalette.ColorRole.Window, QColor(70, 70, 70))
            pal.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        else:
            self._percentile_lbl.setText(f"Percentil {bucket}")
            pal.setColor(QPalette.ColorRole.Window, _BUCKET_COLORS.get(bucket, QColor(180, 180, 180)))
            pal.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        self._percentile_lbl.setPalette(pal)
