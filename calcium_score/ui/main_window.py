"""Main application window wiring the viewer, picker, score table, and menus."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..dicom_loader import load_input, load_pixel_volume
from ..scoring import ARTERIES, Lesion
from ..series_model import Series, Study
from .disclaimer import AboutDialog
from .roi_tools import artery_icon
from .score_table import ScoreTable
from .series_picker import SeriesPickerDialog
from .viewer import SliceIndexLabel, SliceViewer

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agatston Calcium Score — research tool")
        self.resize(1400, 900)

        self._current_series: Series | None = None

        self._build_menu()
        self._build_central()
        self._build_status_bar()

        self._set_tools_enabled(False)
        self.setAcceptDrops(True)

    # ---------- UI scaffold ----------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_folder = QAction("Open &Folder…", self)
        open_folder.setShortcut("Ctrl+O")
        open_folder.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder)

        open_zip = QAction("Open &ZIP…", self)
        open_zip.setShortcut("Ctrl+Shift+O")
        open_zip.triggered.connect(self._open_zip)
        file_menu.addAction(open_zip)

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menubar.addMenu("&Help")
        about = QAction("&About", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_central(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        # Warning bar (non-blocking, only visible when there's a warning)
        self._warning_lbl = QLabel("")
        self._warning_lbl.setWordWrap(True)
        self._warning_lbl.setStyleSheet(
            "background-color: #5a4a20; color: #ffe28a; padding: 6px; font-weight: bold;"
        )
        self._warning_lbl.setVisible(False)
        outer.addWidget(self._warning_lbl)

        # Toolbar for tool/artery selection
        toolbar = QToolBar("Scoring tools")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.setIconSize(QSize(32, 32))

        toolbar.addWidget(QLabel(" Artery: "))
        self._artery_actions: dict[str, QAction] = {}
        self._artery_group = QActionGroup(self)
        self._artery_group.setExclusive(True)
        for artery in ARTERIES:
            act = QAction(artery_icon(artery, size=32), artery, self)
            act.setCheckable(True)
            act.setToolTip(f"Score as {artery}")
            act.setData(artery)
            self._artery_group.addAction(act)
            toolbar.addAction(act)
            self._artery_actions[artery] = act
        self._artery_actions["LAD"].setChecked(True)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Tool: "))
        self._tool_combo = QComboBox()
        self._tool_combo.addItem("Flood-fill (click)", userData=SliceViewer.TOOL_FLOOD)
        self._tool_combo.addItem("Free-hand (click and drag to draw)", userData=SliceViewer.TOOL_POLYGON)
        self._tool_combo.addItem("Eraser (click an ROI to remove it)", userData=SliceViewer.TOOL_ERASER)
        toolbar.addWidget(self._tool_combo)

        toolbar.addSeparator()
        self._undo_btn = QPushButton("Undo last ROI (this slice)")
        self._undo_btn.clicked.connect(self._undo_last)
        toolbar.addWidget(self._undo_btn)

        self._clear_btn = QPushButton("Clear all ROIs")
        self._clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(self._clear_btn)

        # Viewer + score table side-by-side
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._viewer = SliceViewer()
        body_layout.addWidget(self._viewer, stretch=1)

        self._score_table = ScoreTable()
        body_layout.addWidget(self._score_table, stretch=0)

        outer.addWidget(body, stretch=1)
        self.setCentralWidget(central)

        # Wire signals
        self._artery_group.triggered.connect(self._on_artery_changed)
        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        self._viewer.lesion_added.connect(self._on_lesion_added)
        self._viewer.lesions_changed.connect(self._on_lesions_changed)
        self._viewer.slice_changed.connect(self._on_slice_changed)
        self._viewer.cursor_hu_changed.connect(self._on_cursor_hu)
        self._viewer.status_message.connect(self._on_status_message)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._slice_lbl = SliceIndexLabel()
        bar.addPermanentWidget(self._slice_lbl)
        self._hu_lbl = QLabel("HU: —")
        bar.addWidget(self._hu_lbl)

    def _set_tools_enabled(self, enabled: bool) -> None:
        for act in self._artery_actions.values():
            act.setEnabled(enabled)
        self._tool_combo.setEnabled(enabled)
        self._undo_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)

    def _current_artery(self) -> str:
        checked = self._artery_group.checkedAction()
        return checked.data() if checked is not None else "LAD"

    # ---------- actions ----------
    def _open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open DICOM folder")
        if not path:
            return
        self._load(Path(path))

    def _open_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open DICOM ZIP", "", "ZIP archives (*.zip);;All files (*)"
        )
        if not path:
            return
        self._load(Path(path))

    def _load(self, path: Path) -> None:
        progress = QProgressDialog("Reading DICOM headers…", None, 0, 0, self)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(300)
        progress.setCancelButton(None)
        QApplication.processEvents()
        try:
            studies = load_input(path)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Failed to read input", str(exc))
            return
        progress.close()

        if not studies or all(not st.series for st in studies):
            QMessageBox.warning(
                self,
                "No CT series found",
                "Could not find any CT series in the selected input.",
            )
            return

        picker = SeriesPickerDialog(studies, self)
        if picker.exec() != SeriesPickerDialog.DialogCode.Accepted:
            return
        chosen = picker.chosen_series()
        if chosen is None:
            return
        self._open_series(chosen)

    def _open_series(self, series: Series) -> None:
        if series.pixel_spacing is None:
            QMessageBox.critical(
                self,
                "Cannot open series",
                "This series has no PixelSpacing tag, so lesion area in mm² cannot be computed.",
            )
            return

        progress = QProgressDialog("Loading pixel data…", None, 0, 0, self)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        QApplication.processEvents()
        try:
            hu_volume = load_pixel_volume(series)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Failed to load pixels", str(exc))
            return
        progress.close()

        self._current_series = series
        self._viewer.load_volume(hu_volume, series.pixel_spacing)
        self._viewer.set_artery(self._current_artery())
        self._viewer.set_tool(self._tool_combo.currentData())
        self._score_table.clear_lesions()
        self._score_table.set_series_info(series)
        self._set_tools_enabled(True)

        warnings = series.warnings()
        if warnings:
            self._warning_lbl.setText("⚠ " + "  ".join(warnings))
            self._warning_lbl.setVisible(True)
        else:
            self._warning_lbl.setVisible(False)

        self._slice_lbl.update_from(
            self._viewer.state.current_index, hu_volume.shape[0]
        )

    def _on_tool_changed(self, _index: int) -> None:
        tool = self._tool_combo.currentData()
        if tool:
            self._viewer.set_tool(tool)

    def _on_artery_changed(self, action: QAction) -> None:
        artery = action.data()
        if artery:
            self._viewer.set_artery(artery)

    def _on_lesion_added(self, les: Lesion) -> None:
        self._score_table.add_lesion(les)

    def _on_lesions_changed(self) -> None:
        # Triggered by reassignment, undo, or any non-additive change.
        self._score_table.set_lesions(self._viewer.lesions())

    def _on_slice_changed(self, idx: int) -> None:
        if self._viewer.state:
            total = self._viewer.state.hu_volume.shape[0]
            self._slice_lbl.update_from(idx, total)

    def _on_cursor_hu(self, x: int, y: int, hu: float) -> None:
        self._hu_lbl.setText(f"x={x}, y={y}, HU={hu:.0f}")

    def _on_status_message(self, text: str) -> None:
        self.statusBar().showMessage(text, 4000)

    def _undo_last(self) -> None:
        removed = self._viewer.remove_last_lesion()
        if removed is None:
            return
        self._score_table.set_lesions(self._viewer.lesions())

    def _clear_all(self) -> None:
        if not self._viewer.state:
            return
        confirm = QMessageBox.question(
            self,
            "Clear all ROIs",
            "Remove every ROI you've drawn for this series?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        # Re-load the volume to wipe overlays
        assert self._current_series is not None
        self._open_series(self._current_series)

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    # ---------- drag and drop ----------
    @staticmethod
    def _droppable_path_from_urls(urls) -> Path | None:
        """Return the first acceptable folder or .zip path from a list of QUrls."""
        for url in urls:
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            if p.is_dir() or (p.is_file() and p.suffix.lower() == ".zip"):
                return p
        return None

    def _droppable_path(self, event) -> Path | None:
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return None
        return self._droppable_path_from_urls(mime.urls())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._droppable_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._droppable_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._droppable_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._load(path)
