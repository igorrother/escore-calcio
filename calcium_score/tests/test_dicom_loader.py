"""Tests for the DICOM loader using synthetic in-memory DICOM files."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from calcium_score.dicom_loader import load_input, load_pixel_volume
from calcium_score.series_model import Series, Study


def _make_ct_slice(
    path: Path,
    *,
    study_uid: str,
    series_uid: str,
    series_number: int,
    series_description: str,
    slice_thickness: float,
    instance_number: int,
    z: float,
    pixel_value: int = 1024,
) -> None:
    """Write a small synthetic CT DICOM file (8x8 image) to `path`."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    ds.PatientAge = "045Y"
    ds.PatientSex = "M"
    ds.StudyDate = "20260101"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = CTImageStorage
    ds.Modality = "CT"
    ds.SeriesNumber = series_number
    ds.SeriesDescription = series_description
    ds.InstanceNumber = instance_number
    ds.ImagePositionPatient = [0.0, 0.0, z]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.SliceThickness = slice_thickness
    ds.PixelSpacing = [0.5, 0.5]
    ds.KVP = 120.0
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = -1024.0
    ds.Rows = 8
    ds.Columns = 8
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    arr = np.full((8, 8), pixel_value, dtype=np.uint16)
    ds.PixelData = arr.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(str(path), write_like_original=False)


@pytest.fixture
def two_series_folder(tmp_path: Path) -> Path:
    """Folder with two CT series belonging to the same study:
    - series 1: 5 slices, 3mm, description 'CaScore' (candidate)
    - series 2: 3 slices, 0.625mm, description 'Thin axial' (not candidate)
    Plus a junk non-DICOM file that must be skipped.
    """
    study_uid = generate_uid()
    s1_uid = generate_uid()
    s2_uid = generate_uid()
    for i in range(5):
        _make_ct_slice(
            tmp_path / f"s1_{i:02d}.dcm",
            study_uid=study_uid,
            series_uid=s1_uid,
            series_number=1,
            series_description="CaScore Cardiac",
            slice_thickness=3.0,
            instance_number=i + 1,
            z=i * 3.0,
        )
    for i in range(3):
        _make_ct_slice(
            tmp_path / f"s2_{i:02d}.dcm",
            study_uid=study_uid,
            series_uid=s2_uid,
            series_number=2,
            series_description="Thin axial",
            slice_thickness=0.625,
            instance_number=i + 1,
            z=i * 0.625,
        )
    (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")
    return tmp_path


class TestLoadFromFolder:
    def test_groups_series_correctly(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        assert len(studies) == 1
        study = studies[0]
        assert len(study.series) == 2
        s1, s2 = sorted(study.series, key=lambda s: s.series_number or 0)
        assert s1.num_slices == 5
        assert s2.num_slices == 3
        assert s1.slice_thickness == 3.0
        assert s2.slice_thickness == 0.625

    def test_candidate_detection(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        candidates = studies[0].candidate_series()
        assert len(candidates) == 1
        assert candidates[0].series_description == "CaScore Cardiac"

    def test_files_sorted_by_z(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        s1 = next(s for s in studies[0].series if s.series_number == 1)
        # All 5 slice files should be present, in z order
        assert len(s1.file_paths) == 5
        zs = [pydicom.dcmread(p, stop_before_pixels=True).ImagePositionPatient[2]
              for p in s1.file_paths]
        assert zs == sorted(zs)

    def test_patient_info_propagated(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        assert studies[0].patient_name == "Test^Patient"
        assert studies[0].patient_id == "TEST001"
        assert studies[0].patient_age == "045Y"
        assert studies[0].patient_sex == "M"
        assert studies[0].study_date == "20260101"

    def test_skips_non_dicom_files(self, two_series_folder: Path):
        # A txt file is in the folder; it should be silently ignored
        studies = load_input(two_series_folder)
        total = sum(s.num_slices for s in studies[0].series)
        assert total == 8  # 5 + 3, no junk file


class TestLoadFromZip:
    def test_zip_extraction(self, two_series_folder: Path, tmp_path: Path):
        zip_path = tmp_path / "study.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in two_series_folder.glob("*.dcm"):
                zf.write(f, arcname=f.name)
        studies = load_input(zip_path)
        assert len(studies) == 1
        assert sum(s.num_slices for s in studies[0].series) == 8


class TestLoadPixelVolume:
    def test_shape_and_hu_conversion(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        s1 = next(s for s in studies[0].series if s.series_number == 1)
        vol = load_pixel_volume(s1)
        assert vol.shape == (5, 8, 8)
        # Pixel value was 1024, slope 1, intercept -1024 -> HU 0
        assert vol.dtype == np.float32
        assert vol.mean() == 0.0


class TestWarnings:
    def test_thin_slice_warning(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        s2 = next(s for s in studies[0].series if s.series_number == 2)
        warnings = s2.warnings()
        assert any("slice thickness" in w.lower() for w in warnings)

    def test_no_warning_for_3mm(self, two_series_folder: Path):
        studies = load_input(two_series_folder)
        s1 = next(s for s in studies[0].series if s.series_number == 1)
        assert s1.warnings() == []
