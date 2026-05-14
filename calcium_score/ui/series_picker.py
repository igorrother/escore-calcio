"""Modal dialog letting the user pick which CT series to score."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..series_model import Series, Study, annotate_candidates

_COLUMNS = ["Series #", "Description", "Slices", "Thickness (mm)", "KVP", "Candidate"]
_CANDIDATE_BG = QColor(60, 110, 60)


class SeriesPickerDialog(QDialog):
    """Show every CT series across all studies; highlight CAC candidates."""

    def __init__(self, studies: list[Study], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select calcium-scoring series")
        self.resize(900, 480)
        self._chosen: Series | None = None

        layout = QVBoxLayout(self)

        hdr = QLabel(self._patient_header_text(studies))
        font = QFont()
        font.setBold(True)
        hdr.setFont(font)
        layout.addWidget(hdr)

        all_series: list[Series] = []
        for st in studies:
            all_series.extend(st.series)
        pairs = annotate_candidates(all_series)
        # Sort: candidates first, then by series number.
        pairs.sort(key=lambda pair: (not pair[1], pair[0].series_number is None, pair[0].series_number or 0))

        self.table = QTableWidget(len(pairs), len(_COLUMNS), self)
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._series_in_rows: list[Series] = []
        for row, (series, is_cand) in enumerate(pairs):
            self._series_in_rows.append(series)
            cells = [
                str(series.series_number) if series.series_number is not None else "—",
                series.series_description or "(no description)",
                str(series.num_slices),
                f"{series.slice_thickness:g}" if series.slice_thickness is not None else "—",
                f"{series.kvp:g}" if series.kvp is not None else "—",
                "✓" if is_cand else "",
            ]
            for col, txt in enumerate(cells):
                item = QTableWidgetItem(txt)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                if is_cand:
                    item.setBackground(QBrush(_CANDIDATE_BG))
                self.table.setItem(row, col, item)

        if pairs:
            self.table.selectRow(0)
        self.table.doubleClicked.connect(self._accept_selection)
        layout.addWidget(self.table)

        legend = QLabel("Highlighted rows are likely calcium-scoring series.")
        legend.setStyleSheet("color: gray;")
        layout.addWidget(legend)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _patient_header_text(self, studies: list[Study]) -> str:
        if not studies:
            return "No studies found."
        st = studies[0]
        return f"Patient: {st.patient_name or '(unknown)'}    ID: {st.patient_id or '—'}    Study date: {st.study_date or '—'}"

    def _accept_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        self._chosen = self._series_in_rows[idx]
        self.accept()

    def chosen_series(self) -> Series | None:
        return self._chosen
