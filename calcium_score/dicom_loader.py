"""Ingest a folder or ZIP of DICOM files and group them into Studies and Series."""

from __future__ import annotations

import atexit
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

from .series_model import Series, Study

log = logging.getLogger(__name__)


def _safe_get(ds, attr, default=None):
    """Get a DICOM attribute or return default if missing/empty."""
    try:
        val = getattr(ds, attr, default)
    except Exception:
        return default
    if val is None or (
        hasattr(val, "__len__") and len(val) == 0 and not isinstance(val, str)
    ):
        return default
    return val


def _z_position(ds) -> float:
    ipp = _safe_get(ds, "ImagePositionPatient")
    if ipp and len(ipp) >= 3:
        try:
            return float(ipp[2])
        except (TypeError, ValueError):
            pass
    sl = _safe_get(ds, "SliceLocation")
    if sl is not None:
        try:
            return float(sl)
        except (TypeError, ValueError):
            pass
    instance = _safe_get(ds, "InstanceNumber")
    try:
        return float(instance) if instance is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _iter_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".html"}:
                continue
            yield p


def _resolve_input(path: Path) -> Path:
    """Return a directory containing the DICOMs.

    For ZIPs we extract to a tempdir that lives for the process lifetime,
    so DICOM file paths stay valid for lazy pixel loading later.
    """
    if path.is_dir():
        return path
    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="score_app_zip_"))
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp)
        atexit.register(shutil.rmtree, tmp, ignore_errors=True)
        return tmp
    raise ValueError(f"Unsupported input: {path} (expected a directory or .zip)")


def _series_meta_from_ds(ds, study_uid: str, series_uid: str) -> dict:
    ps = _safe_get(ds, "PixelSpacing")
    pixel_spacing: tuple[float, float] | None
    if ps and len(ps) >= 2:
        try:
            pixel_spacing = (float(ps[0]), float(ps[1]))
        except (TypeError, ValueError):
            pixel_spacing = None
    else:
        pixel_spacing = None

    def _as_float(v, default=None):
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _as_int(v, default=None):
        try:
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    return {
        "study_instance_uid": study_uid,
        "series_instance_uid": series_uid,
        "series_number": _as_int(_safe_get(ds, "SeriesNumber")),
        "series_description": str(_safe_get(ds, "SeriesDescription", "") or ""),
        "modality": _safe_get(ds, "Modality", ""),
        "slice_thickness": _as_float(_safe_get(ds, "SliceThickness")),
        "pixel_spacing": pixel_spacing,
        "kvp": _as_float(_safe_get(ds, "KVP")),
        "rescale_slope": _as_float(_safe_get(ds, "RescaleSlope"), 1.0) or 1.0,
        "rescale_intercept": _as_float(_safe_get(ds, "RescaleIntercept"), -1024.0)
        or -1024.0,
        "patient_name": str(_safe_get(ds, "PatientName", "") or ""),
        "patient_id": str(_safe_get(ds, "PatientID", "") or ""),
        "patient_age": str(_safe_get(ds, "PatientAge", "") or ""),
        "patient_sex": str(_safe_get(ds, "PatientSex", "") or ""),
        "study_date": str(_safe_get(ds, "StudyDate", "") or ""),
    }


def load_input(path: str | Path) -> list[Study]:
    """Parse a folder or ZIP of DICOMs and return the list of CT studies found.

    Pixel data is *not* loaded here; only headers. Use `load_pixel_volume`
    later when the user picks a series.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    root = _resolve_input(path)

    per_series_files: dict[tuple[str, str], list[tuple[float, Path]]] = {}
    per_series_meta: dict[tuple[str, str], dict] = {}

    for f in _iter_files(root):
        try:
            ds = pydicom.dcmread(f, force=True, stop_before_pixels=True)
        except (InvalidDicomError, OSError, Exception) as exc:
            log.debug("Skipping %s: %s", f, exc)
            continue

        if _safe_get(ds, "Modality", "") != "CT":
            continue

        study_uid = str(_safe_get(ds, "StudyInstanceUID", ""))
        series_uid = str(_safe_get(ds, "SeriesInstanceUID", ""))
        if not study_uid or not series_uid:
            continue

        key = (study_uid, series_uid)
        per_series_files.setdefault(key, []).append((_z_position(ds), f))
        if key not in per_series_meta:
            per_series_meta[key] = _series_meta_from_ds(ds, study_uid, series_uid)

    studies: dict[str, Study] = {}
    for key, files in per_series_files.items():
        meta = per_series_meta[key]
        sorted_paths = [p for _, p in sorted(files, key=lambda t: t[0])]
        series = Series(file_paths=sorted_paths, **meta)
        study = studies.setdefault(
            meta["study_instance_uid"],
            Study(
                study_instance_uid=meta["study_instance_uid"],
                patient_name=meta["patient_name"],
                patient_id=meta["patient_id"],
                patient_age=meta["patient_age"],
                patient_sex=meta["patient_sex"],
                study_date=meta["study_date"],
            ),
        )
        study.series.append(series)

    for st in studies.values():
        st.series.sort(key=lambda s: (s.series_number is None, s.series_number or 0))

    return list(studies.values())


def load_pixel_volume(series: Series) -> np.ndarray:
    """Load the full 3D HU volume for the given series.

    Returns a float32 array of shape (num_slices, rows, cols) already converted
    to Hounsfield units via the series' rescale slope/intercept.
    """
    slices: list[np.ndarray] = []
    for p in series.file_paths:
        ds = pydicom.dcmread(p)
        slices.append(ds.pixel_array)
    raw = np.stack(slices, axis=0)
    return raw.astype(np.float32) * series.rescale_slope + series.rescale_intercept
