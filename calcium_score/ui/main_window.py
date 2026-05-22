"""Main application window wiring the viewer, picker, score table, and menus."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
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

from .. import __version__
from ..dicom_loader import load_input, load_pixel_volume
from ..scoring import ARTERIES, Lesion
from ..series_model import Series, Study
from ..update_check import (
    UpdateInfo,
    fetch_latest_release_async,
    is_newer_version,
)
from .disclaimer import AboutDialog
from .roi_tools import (
    artery_icon,
    eraser_icon,
    overlay_all_eye_icon,
    overlay_candidate_eye_icon,
)
from .score_table import ScoreTable
from .series_picker import SeriesPickerDialog
from .viewer import SliceIndexLabel, SliceViewer

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    # Emitted from the update-check worker thread; Qt marshals to GUI thread.
    _update_check_finished = Signal(object, bool)  # (UpdateInfo|None, is_manual)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escore de Cálcio de Agatston — ferramenta de pesquisa")
        self.resize(1400, 900)

        self._current_series: Series | None = None

        self._build_menu()
        self._build_central()
        self._build_status_bar()

        self._set_tools_enabled(False)
        self.setAcceptDrops(True)

        self._update_check_finished.connect(self._on_update_check_finished)
        self._kick_off_update_check(manual=False)

    # ---------- UI scaffold ----------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Arquivo")

        open_folder = QAction("Abrir &Pasta…", self)
        open_folder.setShortcut("Ctrl+O")
        open_folder.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder)

        open_zip = QAction("Abrir &ZIP…", self)
        open_zip.setShortcut("Ctrl+Shift+O")
        open_zip.triggered.connect(self._open_zip)
        file_menu.addAction(open_zip)

        file_menu.addSeparator()
        quit_action = QAction("&Sair", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menubar.addMenu("Aj&uda")
        check_updates = QAction("&Verificar atualizações…", self)
        check_updates.triggered.connect(lambda: self._kick_off_update_check(manual=True))
        help_menu.addAction(check_updates)
        help_menu.addSeparator()
        about = QAction("&Sobre", self)
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
        toolbar = QToolBar("Ferramentas de marcação")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.setIconSize(QSize(32, 32))

        toolbar.addWidget(QLabel(" Artéria: "))
        self._artery_actions: dict[str, QAction] = {}
        self._artery_group = QActionGroup(self)
        self._artery_group.setExclusive(True)
        for artery in ARTERIES:
            act = QAction(artery_icon(artery, size=32), artery, self)
            act.setCheckable(True)
            act.setToolTip(f"Marcar como {artery}")
            act.setData(artery)
            self._artery_group.addAction(act)
            toolbar.addAction(act)
            self._artery_actions[artery] = act
        self._artery_actions["DA"].setChecked(True)

        toolbar.addSeparator()
        self._tool_hint_lbl = QLabel(" Clique = preencher · Arraste = mão livre ")
        self._tool_hint_lbl.setToolTip(
            "Um clique simples preenche a calcificação sob o cursor. "
            "Clique e arraste para desenhar uma ROI à mão livre."
        )
        toolbar.addWidget(self._tool_hint_lbl)

        toolbar.addSeparator()
        self._eraser_action = QAction(eraser_icon(32), "Borracha", self)
        self._eraser_action.setCheckable(True)
        self._eraser_action.setToolTip(
            "Borracha — clique em um ROI para removê-la. Desligue para voltar a marcar."
        )
        self._eraser_action.toggled.connect(self._on_eraser_toggled)
        toolbar.addAction(self._eraser_action)

        toolbar.addSeparator()
        self._show_all_action = QAction(overlay_all_eye_icon(32), "Mostrar overlays", self)
        self._show_all_action.setCheckable(True)
        self._show_all_action.setChecked(True)
        self._show_all_action.setToolTip(
            "Mostrar/ocultar todos os overlays (marcação candidata + ROIs). "
            "Se desligado, marcar um novo ROI religa o overlay automaticamente."
        )
        self._show_all_action.toggled.connect(self._on_show_all_toggled)
        toolbar.addAction(self._show_all_action)

        self._show_candidate_action = QAction(overlay_candidate_eye_icon(32), "Mostrar marcação candidata", self)
        self._show_candidate_action.setCheckable(True)
        self._show_candidate_action.setChecked(True)
        self._show_candidate_action.setToolTip(
            "Mostrar/ocultar a marcação rosa das calcificações ≥130 HU "
            "ainda não pontuadas."
        )
        self._show_candidate_action.toggled.connect(self._on_show_candidate_toggled)
        toolbar.addAction(self._show_candidate_action)

        toolbar.addSeparator()
        self._undo_btn = QPushButton("Desfazer último ROI (este corte)")
        self._undo_btn.clicked.connect(self._undo_last)
        toolbar.addWidget(self._undo_btn)

        self._clear_btn = QPushButton("Limpar todos ROIs")
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
        self._viewer.lesion_added.connect(self._on_lesion_added)
        self._viewer.lesions_changed.connect(self._on_lesions_changed)
        self._viewer.slice_changed.connect(self._on_slice_changed)
        self._viewer.cursor_hu_changed.connect(self._on_cursor_hu)
        self._viewer.status_message.connect(self._on_status_message)
        self._viewer.overlay_visibility_changed.connect(self._on_overlay_visibility_changed)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._slice_lbl = SliceIndexLabel()
        bar.addPermanentWidget(self._slice_lbl)
        self._hu_lbl = QLabel("UH: —")
        bar.addWidget(self._hu_lbl)

    def _set_tools_enabled(self, enabled: bool) -> None:
        for act in self._artery_actions.values():
            act.setEnabled(enabled)
        self._tool_hint_lbl.setEnabled(enabled)
        self._eraser_action.setEnabled(enabled)
        self._show_all_action.setEnabled(enabled)
        self._show_candidate_action.setEnabled(enabled)
        self._undo_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)

    def _current_artery(self) -> str:
        checked = self._artery_group.checkedAction()
        return checked.data() if checked is not None else "DA"

    # ---------- actions ----------
    def _open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Abrir pasta DICOM")
        if not path:
            return
        self._load(Path(path))

    def _open_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir ZIP DICOM", "", "Arquivos ZIP (*.zip);;Todos os arquivos (*)"
        )
        if not path:
            return
        self._load(Path(path))

    def _load(self, path: Path) -> None:
        progress = QProgressDialog("Lendo cabeçalhos DICOM…", None, 0, 0, self)
        progress.setWindowTitle("Carregando")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(300)
        progress.setCancelButton(None)
        QApplication.processEvents()
        try:
            studies = load_input(path)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Falha ao ler entrada", str(exc))
            return
        progress.close()

        if not studies or all(not st.series for st in studies):
            QMessageBox.warning(
                self,
                "Nenhuma série de TC encontrada",
                "Nenhuma série de TC foi encontrada na entrada selecionada.",
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
                "Não foi possível abrir a série",
                "Esta série não tem a tag PixelSpacing, então a área da lesão em mm² não pode ser calculada.",
            )
            return

        progress = QProgressDialog("Carregando dados de pixel…", None, 0, 0, self)
        progress.setWindowTitle("Carregando")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        QApplication.processEvents()
        try:
            hu_volume = load_pixel_volume(series)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Falha ao carregar pixels", str(exc))
            return
        progress.close()

        self._current_series = series
        self._viewer.load_volume(hu_volume, series.pixel_spacing)
        self._viewer.set_artery(self._current_artery())
        self._viewer.set_tool(SliceViewer.TOOL_AUTO)
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

    def _on_show_all_toggled(self, checked: bool) -> None:
        # "All overlays" toggle drives both viewer flags. The candidate
        # sub-toggle is moot while "all" is off — re-apply its checked
        # state when "all" comes back on.
        self._viewer.set_lesion_overlays_visible(checked)
        self._viewer.set_candidate_overlay_visible(
            checked and self._show_candidate_action.isChecked()
        )

    def _on_show_candidate_toggled(self, checked: bool) -> None:
        # Only meaningful while "all overlays" is on.
        if self._show_all_action.isChecked():
            self._viewer.set_candidate_overlay_visible(checked)

    def _on_overlay_visibility_changed(self) -> None:
        # Viewer auto-restored the lesion overlay after a score in the
        # "all hidden" state. Sync the toolbar toggle's visual state.
        self._show_all_action.blockSignals(True)
        self._show_all_action.setChecked(True)
        self._show_all_action.blockSignals(False)
        # Respect the user's candidate-toggle intent: don't override it.
        self._viewer.set_candidate_overlay_visible(self._show_candidate_action.isChecked())

    def _on_eraser_toggled(self, checked: bool) -> None:
        self._viewer.set_tool(
            SliceViewer.TOOL_ERASER if checked else SliceViewer.TOOL_AUTO
        )

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
        self._hu_lbl.setText(f"x={x}, y={y}, UH={hu:.0f}")

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
            "Limpar todas as ROIs",
            "Remover todas as ROIs marcadas nesta série?",
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

    # ---------- update check ----------
    def _kick_off_update_check(self, manual: bool) -> None:
        fetch_latest_release_async(
            lambda info: self._update_check_finished.emit(info, manual)
        )

    def _on_update_check_finished(self, info: UpdateInfo | None, manual: bool) -> None:
        if info is None:
            if manual:
                QMessageBox.warning(
                    self,
                    "Verificação de atualizações",
                    "Não foi possível verificar atualizações. "
                    "Verifique sua conexão com a internet e tente novamente.",
                )
            return

        if not is_newer_version(info.latest_version, __version__):
            if manual:
                QMessageBox.information(
                    self,
                    "Verificação de atualizações",
                    f"Você já está usando a versão mais recente (v{__version__}).",
                )
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Atualização disponível")
        box.setText(
            f"Uma nova versão está disponível: <b>{info.latest_version}</b><br>"
            f"Você está usando v{__version__}."
        )
        box.setInformativeText(
            "Abra a página de releases para baixar a versão mais recente."
        )
        download_btn = box.addButton("Abrir página de download", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Mais tarde", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is download_btn:
            QDesktopServices.openUrl(QUrl(info.release_url))

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
