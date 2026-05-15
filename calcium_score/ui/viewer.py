"""Slice viewer with flood-fill and polygon ROI tools."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..scoring import HU_THRESHOLD, Lesion, score_flood_fill, score_polygon
from .roi_tools import CANDIDATE_COLOR, artery_color


@dataclass
class ViewerState:
    """In-memory state for the loaded series."""

    hu_volume: np.ndarray  # shape (slices, rows, cols), float32
    pixel_area_mm2: float
    current_index: int = 0
    window_width: float = 800.0
    window_level: float = 300.0  # cardiac CT default


def _hu_to_qimage(hu: np.ndarray, window: float, level: float) -> QImage:
    """Apply windowing and convert an HU slice to a grayscale QImage."""
    lo = level - window / 2.0
    hi = level + window / 2.0
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((hu - lo) / (hi - lo), 0.0, 1.0)
    img8 = (scaled * 255).astype(np.uint8)
    h, w = img8.shape
    # Make contiguous copy so QImage doesn't reference freed memory
    img8 = np.ascontiguousarray(img8)
    qimg = QImage(img8.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    return qimg


class SliceViewer(QGraphicsView):
    """QGraphicsView showing one slice at a time, with ROI tools.

    Emits:
      lesion_added(Lesion)
      slice_changed(int)
      cursor_hu_changed(int x, int y, float hu) — for status bar
    """

    lesion_added = Signal(Lesion)
    slice_changed = Signal(int)
    cursor_hu_changed = Signal(int, int, float)
    status_message = Signal(str)

    TOOL_FLOOD = "flood"
    TOOL_POLYGON = "polygon"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QColor(0, 0, 0))

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._overlay_items: list[QGraphicsItem] = []
        self.state: ViewerState | None = None

        # Lesions keyed by slice index, list of (Lesion, overlay item)
        self._lesions_by_slice: dict[int, list[Lesion]] = {}

        # Tool state
        self.active_tool: str = self.TOOL_FLOOD
        self.active_artery: str = "LAD"

        # Free-hand polygon drafting state
        self._poly_points: list[QPointF] = []
        self._drawing_polygon: bool = False
        self._preview_item: QGraphicsPathItem | None = None

        # Right-button window/level drag
        self._wl_start: QPoint | None = None
        self._wl_initial: tuple[float, float] | None = None

    # ---------- public API ----------
    def load_volume(self, hu_volume: np.ndarray, pixel_spacing: tuple[float, float]) -> None:
        area = float(pixel_spacing[0]) * float(pixel_spacing[1])
        self.state = ViewerState(
            hu_volume=hu_volume,
            pixel_area_mm2=area,
            current_index=hu_volume.shape[0] // 2,
        )
        self._lesions_by_slice.clear()
        self._render_slice()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.slice_changed.emit(self.state.current_index)

    def set_tool(self, tool: str) -> None:
        if tool not in (self.TOOL_FLOOD, self.TOOL_POLYGON):
            return
        self.active_tool = tool
        self._cancel_polygon_preview()

    def set_artery(self, artery: str) -> None:
        self.active_artery = artery

    def set_slice(self, index: int) -> None:
        if not self.state:
            return
        n = self.state.hu_volume.shape[0]
        index = max(0, min(n - 1, index))
        if index == self.state.current_index:
            return
        self.state.current_index = index
        self._cancel_polygon_preview()
        self._render_slice()
        self.slice_changed.emit(index)

    def lesions(self) -> list[Lesion]:
        out: list[Lesion] = []
        for arr in self._lesions_by_slice.values():
            out.extend(arr)
        return out

    def remove_last_lesion(self) -> Lesion | None:
        if not self.state:
            return None
        arr = self._lesions_by_slice.get(self.state.current_index)
        if not arr:
            # Fall back to whichever slice has the most-recently-added lesion?
            # For simplicity v1 only undoes lesions on the current slice.
            return None
        les = arr.pop()
        if not arr:
            del self._lesions_by_slice[self.state.current_index]
        self._render_slice()
        return les

    # ---------- rendering ----------
    def _render_slice(self) -> None:
        if not self.state:
            return
        self._scene.clear()
        self._overlay_items.clear()

        hu_slice = self.state.hu_volume[self.state.current_index]
        qimg = _hu_to_qimage(hu_slice, self.state.window_width, self.state.window_level)
        self._pixmap_item = self._scene.addPixmap(QPixmap.fromImage(qimg))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

        # Draw a translucent tint over candidate calcium that hasn't been
        # scored yet, so the user can see where to click.
        self._draw_candidate_overlay(hu_slice)

        # Draw overlays for lesions on this slice
        for les in self._lesions_by_slice.get(self.state.current_index, []):
            self._draw_lesion_overlay(les)

        # Free-hand polygon preview is managed separately as a persistent
        # QGraphicsPathItem (see _start/_extend/_cancel_polygon_preview)
        # because re-rendering the whole scene on every mouse move would
        # be wasteful. _render_slice clears the scene, so any in-progress
        # preview is implicitly dropped — callers must cancel first.

    def _existing_mask_on_slice(self, slice_idx: int) -> np.ndarray | None:
        """Union of all existing ROI masks on a slice, or None if no ROIs yet."""
        arr = self._lesions_by_slice.get(slice_idx, [])
        if not arr:
            return None
        out = np.zeros_like(arr[0].mask)
        for les in arr:
            out |= les.mask
        return out

    def _draw_candidate_overlay(self, hu_slice: np.ndarray) -> None:
        """Tint pixels >=130 HU that are not yet part of any ROI on this slice."""
        candidate = hu_slice >= HU_THRESHOLD
        if not candidate.any():
            return
        existing = self._existing_mask_on_slice(self.state.current_index)
        if existing is not None:
            candidate &= ~existing
            if not candidate.any():
                return
        h, w = candidate.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[candidate, 0] = CANDIDATE_COLOR.red()
        rgba[candidate, 1] = CANDIDATE_COLOR.green()
        rgba[candidate, 2] = CANDIDATE_COLOR.blue()
        rgba[candidate, 3] = CANDIDATE_COLOR.alpha()
        rgba = np.ascontiguousarray(rgba)
        qimg = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        item = self._scene.addPixmap(QPixmap.fromImage(qimg))
        # Below ROI overlays (zValue=1) but above the slice (default 0)
        item.setZValue(0.5)
        self._overlay_items.append(item)

    # ---------- free-hand polygon preview ----------
    def _start_polygon_preview(self, p: QPointF) -> None:
        self._cancel_polygon_preview()
        self._poly_points = [p]
        self._drawing_polygon = True
        path = QPainterPath(p)
        pen = QPen(QColor(255, 255, 0))
        pen.setWidthF(1.5)  # thick while user is drawing
        pen.setCosmetic(False)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setZValue(2)
        self._scene.addItem(item)
        self._preview_item = item

    def _extend_polygon_preview(self, p: QPointF) -> None:
        if not self._preview_item or not self._poly_points:
            return
        # Skip near-duplicate points to keep the polygon array compact
        last = self._poly_points[-1]
        if (p - last).manhattanLength() < 1:
            return
        self._poly_points.append(p)
        path = self._preview_item.path()
        path.lineTo(p)
        self._preview_item.setPath(path)

    def _cancel_polygon_preview(self) -> None:
        self._drawing_polygon = False
        self._poly_points = []
        if self._preview_item is not None:
            self._scene.removeItem(self._preview_item)
            self._preview_item = None

    def _draw_lesion_overlay(self, les: Lesion) -> None:
        """Render a translucent colored mask for a lesion."""
        color = artery_color(les.artery)
        mask = les.mask
        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[mask, 0] = color.red()
        rgba[mask, 1] = color.green()
        rgba[mask, 2] = color.blue()
        rgba[mask, 3] = color.alpha()
        # Need a contiguous buffer for QImage
        rgba = np.ascontiguousarray(rgba)
        qimg = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        item = self._scene.addPixmap(QPixmap.fromImage(qimg))
        item.setZValue(1)
        self._overlay_items.append(item)

    # ---------- input handlers ----------
    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.state:
            return
        steps = event.angleDelta().y() // 120
        if steps == 0:
            return
        # Scroll up -> previous slice
        self.set_slice(self.state.current_index - int(steps))

    def keyPressEvent(self, event) -> None:
        if not self.state:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_PageUp:
            self.set_slice(self.state.current_index - 1)
        elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_PageDown:
            self.set_slice(self.state.current_index + 1)
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_polygon_preview()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.state or not self._pixmap_item:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.RightButton:
            # Start window/level drag
            self._wl_start = event.pos()
            self._wl_initial = (self.state.window_width, self.state.window_level)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            x = int(scene_pos.x())
            y = int(scene_pos.y())
            hu_slice = self.state.hu_volume[self.state.current_index]
            if not (0 <= x < hu_slice.shape[1] and 0 <= y < hu_slice.shape[0]):
                return

            if self.active_tool == self.TOOL_FLOOD:
                existing = self._existing_mask_on_slice(self.state.current_index)
                if existing is not None and existing[y, x]:
                    self.status_message.emit(
                        "That pixel is already part of an existing ROI. Undo first if you want to re-score."
                    )
                    return
                les = score_flood_fill(
                    hu_slice,
                    (y, x),
                    self.state.pixel_area_mm2,
                    artery=self.active_artery,
                    slice_index=self.state.current_index,
                )
                if les is None:
                    return
                if existing is not None and (les.mask & existing).any():
                    self.status_message.emit(
                        "This calcification overlaps an existing ROI. Undo first if you want to re-score."
                    )
                    return
                self._add_lesion(les)
            elif self.active_tool == self.TOOL_POLYGON:
                self._start_polygon_preview(QPointF(x, y))

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.state:
            super().mouseMoveEvent(event)
            return

        if self._wl_start is not None and self._wl_initial is not None:
            dx = event.pos().x() - self._wl_start.x()
            dy = event.pos().y() - self._wl_start.y()
            w0, l0 = self._wl_initial
            self.state.window_width = max(1.0, w0 + dx * 4.0)
            self.state.window_level = l0 + dy * 4.0
            self._render_slice()
            return

        if self._pixmap_item:
            scene_pos = self.mapToScene(event.pos())
            x = int(scene_pos.x())
            y = int(scene_pos.y())
            hu_slice = self.state.hu_volume[self.state.current_index]
            in_bounds = 0 <= x < hu_slice.shape[1] and 0 <= y < hu_slice.shape[0]

            # Extend the free-hand polygon while the user is dragging.
            if self._drawing_polygon and in_bounds:
                self._extend_polygon_preview(QPointF(x, y))

            if in_bounds:
                self.cursor_hu_changed.emit(x, y, float(hu_slice[y, x]))

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._wl_start = None
            self._wl_initial = None
            return
        if event.button() == Qt.MouseButton.LeftButton and self._drawing_polygon:
            self._finish_polygon_drag()
            return
        super().mouseReleaseEvent(event)

    def _finish_polygon_drag(self) -> None:
        """Close the free-hand polygon and score it (or cancel if too small)."""
        if not self.state:
            self._cancel_polygon_preview()
            return
        points = list(self._poly_points)
        # Always clear preview before re-rendering the slice
        self._cancel_polygon_preview()
        if len(points) < 3:
            return  # accidental click without a drag
        hu_slice = self.state.hu_volume[self.state.current_index]
        poly = np.array([[p.x(), p.y()] for p in points], dtype=float)
        les = score_polygon(
            hu_slice,
            poly,
            self.state.pixel_area_mm2,
            artery=self.active_artery,
            slice_index=self.state.current_index,
        )
        if les is None:
            self._render_slice()
            return
        existing = self._existing_mask_on_slice(self.state.current_index)
        if existing is not None and (les.mask & existing).any():
            self.status_message.emit(
                "Polygon overlaps an existing ROI. Undo first if you want to re-score."
            )
            self._render_slice()
            return
        self._add_lesion(les)

    def _add_lesion(self, les: Lesion) -> None:
        self._lesions_by_slice.setdefault(les.slice_index, []).append(les)
        self._render_slice()
        self.lesion_added.emit(les)


class SliceIndexLabel(QLabel):
    """Small helper widget that shows '<current>/<total>'."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setText("- / -")

    def update_from(self, current: int, total: int) -> None:
        self.setText(f"{current + 1} / {total}")
