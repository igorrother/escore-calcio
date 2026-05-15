"""
Pure Agatston coronary artery calcium scoring.

No Qt, pydicom, or file I/O is allowed in this module. Everything here
operates on numpy arrays of Hounsfield units and returns plain dataclasses
so it can be unit-tested without a GUI or DICOM files.

References:
- Agatston AS, et al. JACC 1990.
- Standard threshold: HU >= 130. Minimum lesion area: 1 mm^2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from skimage.draw import polygon as sk_polygon
from skimage.measure import label

HU_THRESHOLD: int = 130
MIN_LESION_AREA_MM2: float = 1.0

ARTERIES: tuple[str, ...] = ("TCE", "DA", "Cx", "CD", "DP")


@dataclass
class Lesion:
    """A single calcified region scored on one slice."""

    artery: str
    slice_index: int
    area_mm2: float
    max_hu: float
    score: float
    mask: np.ndarray = field(repr=False)  # bool array, same shape as the slice


def density_weight(max_hu: float) -> int:
    """Agatston density weighting factor based on the maximum HU in a lesion.

    130-199 -> 1, 200-299 -> 2, 300-399 -> 3, >=400 -> 4.
    Returns 0 if max_hu is below the 130 HU threshold (no lesion).
    """
    if max_hu < HU_THRESHOLD:
        return 0
    if max_hu < 200:
        return 1
    if max_hu < 300:
        return 2
    if max_hu < 400:
        return 3
    return 4


def lesion_score(area_mm2: float, max_hu: float) -> float:
    """Agatston score for a single lesion: area (mm^2) * weight.

    Returns 0 if the lesion is too small (< 1 mm^2) or below threshold.
    """
    if area_mm2 < MIN_LESION_AREA_MM2:
        return 0.0
    w = density_weight(max_hu)
    if w == 0:
        return 0.0
    return float(area_mm2) * w


def risk_category(total: float) -> str:
    """Standard Agatston risk classification for total CAC score (pt-BR)."""
    if total <= 0:
        return "nenhum"
    if total <= 10:
        return "mínimo"
    if total <= 100:
        return "leve"
    if total <= 400:
        return "moderado"
    return "Acentuado"


def _score_mask(
    hu_slice: np.ndarray,
    mask: np.ndarray,
    pixel_area_mm2: float,
    *,
    artery: str,
    slice_index: int,
) -> Lesion | None:
    """Build a Lesion from a boolean mask of pixels >=130 HU.

    Returns None if the mask is empty after threshold filtering.
    The mask passed in must already be the calcified region (>=130 HU pixels only).
    """
    if not mask.any():
        return None
    area_mm2 = float(mask.sum()) * float(pixel_area_mm2)
    max_hu = float(hu_slice[mask].max())
    score = lesion_score(area_mm2, max_hu)
    return Lesion(
        artery=artery,
        slice_index=slice_index,
        area_mm2=area_mm2,
        max_hu=max_hu,
        score=score,
        mask=mask.astype(bool),
    )


def score_flood_fill(
    hu_slice: np.ndarray,
    seed_yx: tuple[int, int],
    pixel_area_mm2: float,
    *,
    artery: str,
    slice_index: int,
) -> Lesion | None:
    """Score the connected component of >=130 HU pixels containing the seed.

    Uses 4-connectivity (skimage default for label with connectivity=1).
    Returns None if the seed pixel is not above threshold or no calcium
    is connected to it.
    """
    y, x = seed_yx
    if not (0 <= y < hu_slice.shape[0] and 0 <= x < hu_slice.shape[1]):
        return None
    if hu_slice[y, x] < HU_THRESHOLD:
        return None

    binary = hu_slice >= HU_THRESHOLD
    labels = label(binary, connectivity=1)
    target = labels[y, x]
    if target == 0:
        return None
    component_mask = labels == target
    return _score_mask(
        hu_slice,
        component_mask,
        pixel_area_mm2,
        artery=artery,
        slice_index=slice_index,
    )


def score_polygon(
    hu_slice: np.ndarray,
    polygon_xy: np.ndarray,
    pixel_area_mm2: float,
    *,
    artery: str,
    slice_index: int,
) -> Lesion | None:
    """Score pixels >=130 HU inside a user-drawn polygon.

    polygon_xy is an (N, 2) array of (x, y) vertices in pixel coordinates.
    """
    polygon_xy = np.asarray(polygon_xy)
    if polygon_xy.ndim != 2 or polygon_xy.shape[0] < 3:
        return None

    rr, cc = sk_polygon(
        polygon_xy[:, 1],  # rows = y
        polygon_xy[:, 0],  # cols = x
        shape=hu_slice.shape,
    )
    poly_mask = np.zeros(hu_slice.shape, dtype=bool)
    poly_mask[rr, cc] = True
    calcium_mask = poly_mask & (hu_slice >= HU_THRESHOLD)
    return _score_mask(
        hu_slice,
        calcium_mask,
        pixel_area_mm2,
        artery=artery,
        slice_index=slice_index,
    )


def filter_small_components(
    mask: np.ndarray,
    pixel_area_mm2: float,
    min_area_mm2: float = MIN_LESION_AREA_MM2,
) -> np.ndarray:
    """Keep only connected components of `mask` whose area is >= min_area_mm2.

    Returns a new boolean array of the same shape with sub-threshold blobs
    removed. Used to filter image noise out of the candidate-calcium overlay
    so we don't paint pixels that can never be scored.
    """
    if not mask.any() or pixel_area_mm2 <= 0:
        return mask.astype(bool, copy=True)
    min_pixels = int(np.ceil(min_area_mm2 / pixel_area_mm2))
    if min_pixels <= 1:
        return mask.astype(bool, copy=True)
    labels = label(mask, connectivity=1)
    if labels.max() == 0:
        return mask.astype(bool, copy=True)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_pixels
    keep[0] = False  # background label always rejected
    return keep[labels]


def totals_by_artery(lesions: Iterable[Lesion]) -> dict[str, float]:
    """Sum lesion scores grouped by artery, returning every artery (zeros included)."""
    out: dict[str, float] = {a: 0.0 for a in ARTERIES}
    for les in lesions:
        if les.artery in out:
            out[les.artery] += les.score
    return out


def grand_total(lesions: Iterable[Lesion]) -> float:
    return float(sum(les.score for les in lesions))


def pixel_area_mm2(pixel_spacing: tuple[float, float] | list[float]) -> float:
    """Convenience: DICOM PixelSpacing -> per-pixel area in mm^2."""
    row_mm, col_mm = pixel_spacing[0], pixel_spacing[1]
    return float(row_mm) * float(col_mm)


def hu_from_raw(
    pixel_array: np.ndarray,
    rescale_slope: float = 1.0,
    rescale_intercept: float = -1024.0,
) -> np.ndarray:
    """Apply DICOM rescale slope/intercept to obtain Hounsfield units."""
    return pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
