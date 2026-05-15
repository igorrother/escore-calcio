# CLAUDE.md — escore-calcio (Agatston Calcium Score)

## Project purpose

Research / educational Windows desktop tool for **manual Agatston coronary artery calcium (CAC) scoring** from cardiac CT DICOM studies.

**This is not a medical device. Not for clinical diagnosis.** All UI surfaces and the About dialog must state this clearly.

## Stack

- Python 3.11+
- PySide6 (Qt for Python)
- pydicom — DICOM parsing
- numpy — image math
- scikit-image — connected components (`skimage.measure.label`) and polygon rasterization (`skimage.draw.polygon`)

Install: `pip install -r requirements.txt`

## Run

```
python main.py
```

Tests:

```
python -m pytest
```

## Layout

```
escore-calcio/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── main.py
└── calcium_score/
    ├── __init__.py
    ├── dicom_loader.py        # folder + ZIP ingestion, series grouping
    ├── series_model.py        # Series/Study dataclasses, candidate detection
    ├── scoring.py             # pure Agatston math — no Qt or pydicom imports
    ├── ui/
    │   ├── __init__.py
    │   ├── main_window.py
    │   ├── disclaimer.py
    │   ├── series_picker.py
    │   ├── viewer.py
    │   ├── roi_tools.py
    │   └── score_table.py
    └── tests/
        ├── __init__.py
        ├── test_scoring.py
        └── test_dicom_loader.py
```

## Agatston scoring rules (authoritative — do not drift)

- HU threshold: a pixel counts toward a lesion only if HU ≥ **130**.
- Minimum lesion area: a connected calcified region must be ≥ **1 mm²** (otherwise score = 0).
- Density weighting factor (W) from the **maximum** HU within the lesion:
  - 130–199 → W = 1
  - 200–299 → W = 2
  - 300–399 → W = 3
  - ≥ 400  → W = 4
- Lesion score = area (mm²) × W
- Total Agatston = sum over all lesions in all slices.
- HU conversion from raw DICOM pixel: `HU = pixel * RescaleSlope + RescaleIntercept` (defaults 1 and -1024).
- Pixel area: `PixelSpacing[0] * PixelSpacing[1]` (mm²).
- Standard acquisition: **3 mm** axial non-contrast ECG-gated CT. Non-3mm series are warned but allowed.

### Risk categories

- 0 → none
- 1–10 → minimal
- 11–100 → mild
- 101–400 → moderate
- > 400 → severe

## Coronary arteries (UI vocabulary)

User must pick the artery before each ROI is created. Allowed values, in this order:

`LM, LAD, LCx, RCA, PDA`

## Coding conventions

- Type hints everywhere.
- `@dataclass` for `Lesion`, `Series`, `Study`.
- `scoring.py` is **pure** — no Qt, no pydicom, no file I/O. Easy to unit-test.
- `dicom_loader.py` is the only place pydicom is imported outside the UI layer.
- UI lives under `calcium_score/ui/` and is the only place PySide6 is imported.
- No deep-learning, no automatic detection in v1.

## Git workflow

- Repository is **private and local** (no remote unless the user asks).
- Commit at the end of each meaningful step. Don't accumulate giant uncommitted diffs.
- Conventional Commits style: `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`.
- Run `python -m pytest` before any commit that touches `scoring.py` or `dicom_loader.py`.
- **Never commit DICOM files, ZIPs, or patient data.** `.gitignore` blocks `*.dcm`, `*.zip`, `sample_data/`, `data/`.

## Known limitations (v1)

- Manual ROIs only — no automatic lesion detection.
- User must assign each ROI to an artery; no automatic vessel labeling.
- Slice thickness ≠ 3 mm: warning only, no correction factor applied.
- No CSV/PDF export, no session save/load.
- No 3D / MPR / volume rendering.
- No DICOM anonymization or send.
