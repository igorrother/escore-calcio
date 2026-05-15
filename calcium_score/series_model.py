"""Data model for DICOM studies and series + calcium-score candidate detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Regex for series descriptions that typically indicate a calcium-scoring scan.
_CAC_DESCRIPTION_RE = re.compile(r"cac|calc|score|cas|agatston", re.IGNORECASE)

# Slice thickness range that we treat as a plausible CAC protocol.
_THICKNESS_MIN_MM = 2.0
_THICKNESS_MAX_MM = 3.5
_STANDARD_THICKNESS_MM = 3.0


@dataclass
class Series:
    """A single DICOM series (one image stack)."""

    study_instance_uid: str
    series_instance_uid: str
    series_number: int | None
    series_description: str
    modality: str
    slice_thickness: float | None
    pixel_spacing: tuple[float, float] | None
    kvp: float | None
    rescale_slope: float
    rescale_intercept: float
    # Patient/study info convenient to have on the series
    patient_name: str
    patient_id: str
    patient_age: str
    patient_sex: str
    study_date: str
    # File paths sorted by z-position (ImagePositionPatient[2]) ascending
    file_paths: list[Path] = field(default_factory=list)

    @property
    def num_slices(self) -> int:
        return len(self.file_paths)

    def is_candidate(self, max_slices_in_study: int | None = None) -> bool:
        """True if this series looks like a calcium-scoring scan.

        Heuristic: thickness in [2.0, 3.5] mm AND (description matches the
        regex OR it is the largest-by-slice-count series in the study at
        exactly 3 mm).
        """
        if self.modality != "CT":
            return False
        if self.slice_thickness is None:
            return False
        if not (_THICKNESS_MIN_MM <= self.slice_thickness <= _THICKNESS_MAX_MM):
            return False
        if _CAC_DESCRIPTION_RE.search(self.series_description or ""):
            return True
        if (
            max_slices_in_study is not None
            and abs(self.slice_thickness - _STANDARD_THICKNESS_MM) < 0.05
            and self.num_slices == max_slices_in_study
        ):
            return True
        return False

    def warnings(self) -> list[str]:
        """Non-blocking warnings shown to the user after they pick this series."""
        out: list[str] = []
        if self.slice_thickness is None:
            out.append(
                "Espessura de fatia ausente no cabeçalho DICOM; o escore de "
                "Agatston pode ser pouco confiável."
            )
        elif abs(self.slice_thickness - _STANDARD_THICKNESS_MM) >= 0.05:
            out.append(
                f"Espessura de fatia {self.slice_thickness:g} mm difere do "
                "protocolo padrão de Agatston de 3 mm; os totais podem não ser "
                "comparáveis aos valores de referência."
            )
        if self.pixel_spacing is None:
            out.append(
                "Espaçamento de pixel ausente; não é possível calcular a área da lesão em mm²."
            )
        return out


@dataclass
class Study:
    """A DICOM study, holding one or more CT series."""

    study_instance_uid: str
    patient_name: str
    patient_id: str
    patient_age: str
    patient_sex: str
    study_date: str
    series: list[Series] = field(default_factory=list)

    @property
    def max_slices(self) -> int:
        return max((s.num_slices for s in self.series), default=0)

    def candidate_series(self) -> list[Series]:
        m = self.max_slices
        return [s for s in self.series if s.is_candidate(m)]


def annotate_candidates(series_list: Iterable[Series]) -> list[tuple[Series, bool]]:
    """Pair each series with a boolean indicating whether it's a CAC candidate.

    Useful for the picker UI which wants a flat list across all studies.
    """
    series_list = list(series_list)
    by_study: dict[str, int] = {}
    for s in series_list:
        by_study[s.study_instance_uid] = max(
            by_study.get(s.study_instance_uid, 0), s.num_slices
        )
    return [(s, s.is_candidate(by_study.get(s.study_instance_uid))) for s in series_list]
