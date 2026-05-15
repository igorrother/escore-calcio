# score_app — Agatston Calcium Score (research/educational)

Windows desktop tool for manually scoring coronary artery calcium from a non-contrast cardiac CT DICOM study using the Agatston method.

> **Not a medical device. Not for clinical diagnosis. Research and educational use only.**

## Install

Requires Python 3.11+.

```
pip install -r requirements.txt
```

## Run

```
python main.py
```

## Workflow

1. Accept the research-use-only disclaimer at startup.
2. `File → Open Folder…` or `File → Open ZIP…`, **or just drag a folder/ZIP onto the window**.
3. Pick the calcium-scoring CT series (candidates are auto-flagged).
4. Scroll through slices, pick an artery (LM / LAD / LCx / RCA / PDA), pick a tool:
   - **Flood-fill** — click on a calcification; the app grows a region of all touching pixels ≥ 130 HU.
   - **Free-hand** — click and drag a closed loop around an area; only pixels ≥ 130 HU inside count. Press Esc to cancel mid-draw.
5. The score table on the right updates live: per-artery totals, grand total Agatston score, risk category.

## Scoring rules

- Pixel counts if HU ≥ 130.
- Lesion must be ≥ 1 mm² to score.
- Weight by max HU in lesion: 130–199 → 1, 200–299 → 2, 300–399 → 3, ≥ 400 → 4.
- Lesion score = area (mm²) × weight; total = sum across all lesions.
- Risk: 0 = none, 1–10 = minimal, 11–100 = mild, 101–400 = moderate, > 400 = severe.

## Tests

```
python -m pytest
```
