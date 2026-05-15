"""
MESA coronary artery calcium percentile reference.

Source: McClelland RL, Chung H, Detrano R, Post W, Kronmal RA.
"Distribution of Coronary Artery Calcium by Race, Gender, and Age:
Results from the Multi-Ethnic Study of Atherosclerosis (MESA)."
Circulation. 2006;113:30-37. DOI: 10.1161/CIRCULATIONAHA.105.580696

Table 2 of that paper gives estimated CAC thresholds at the 25th, 50th,
75th and 90th percentiles for each combination of:
  - race/ethnicity (White, Chinese, Black, Hispanic)
  - sex (M / F)
  - 10-year age band (45-54, 55-64, 65-74, 75-84)

Per the paper: "For these calculations, the percentile was estimated at
the midpoint of the age range" — i.e. ages 50, 60, 70, 80. We linearly
interpolate between adjacent midpoints for in-between ages, and clamp
to the endpoints below 50 / above 80 (but still within the published
45-84 range).

The functions here are pure (no UI imports) so they're easy to unit-test.
"""

from __future__ import annotations

from typing import Literal

Race = Literal["white", "chinese", "black", "hispanic"]
Sex = Literal["M", "F"]

RACE_CODES: tuple[Race, ...] = ("white", "chinese", "black", "hispanic")
SEX_CODES: tuple[Sex, ...] = ("M", "F")
BUCKETS: tuple[str, ...] = ("<25", "25-50", "50-75", "75-90", ">90")

AGE_MIN = 45
AGE_MAX = 84

# Table 2 from McClelland 2006. Each leaf is [p25, p50, p75, p90] at the
# midpoint of the age band.
MESA_TABLE: dict[Race, dict[Sex, dict[int, list[float]]]] = {
    "white": {
        "F": {
            50: [0, 0, 0, 8],
            60: [0, 0, 16, 102],
            70: [0, 13, 119, 391],
            80: [20, 106, 370, 921],
        },
        "M": {
            50: [0, 0, 22, 110],
            60: [0, 28, 155, 452],
            70: [21, 145, 540, 1345],
            80: [103, 385, 1200, 2933],
        },
    },
    "chinese": {
        "F": {
            50: [0, 0, 0, 12],
            60: [0, 0, 18, 105],
            70: [0, 5, 70, 246],
            80: [0, 32, 146, 398],
        },
        "M": {
            50: [0, 0, 14, 89],
            60: [0, 5, 67, 242],
            70: [0, 34, 174, 487],
            80: [11, 81, 305, 769],
        },
    },
    "black": {
        "F": {
            50: [0, 0, 0, 9],
            60: [0, 0, 5, 74],
            70: [0, 0, 77, 310],
            80: [0, 47, 214, 582],
        },
        "M": {
            50: [0, 0, 2, 45],
            60: [0, 0, 40, 173],
            70: [0, 32, 191, 575],
            80: [23, 141, 516, 1281],
        },
    },
    "hispanic": {
        "F": {
            50: [0, 0, 0, 2],
            60: [0, 0, 2, 50],
            70: [0, 1, 51, 203],
            80: [0, 45, 205, 557],
        },
        "M": {
            50: [0, 0, 9, 88],
            60: [0, 3, 75, 291],
            70: [1, 56, 247, 666],
            80: [36, 153, 494, 1221],
        },
    },
}


def parse_dicom_age_years(age: str) -> float | None:
    """Parse a DICOM AS value (e.g. '045Y') to a float in years.

    Returns None if the string is empty or doesn't match the expected
    NNN[YMWD] pattern.
    """
    if not age or len(age) < 4:
        return None
    try:
        n = int(age[:3])
    except ValueError:
        return None
    unit = age[3].upper()
    if unit == "Y":
        return float(n)
    if unit == "M":
        return n / 12.0
    if unit == "W":
        return n / 52.0
    if unit == "D":
        return n / 365.0
    return None


def percentile_thresholds(age: float, sex: str, race: str) -> list[float] | None:
    """Return [p25, p50, p75, p90] CAC thresholds interpolated by age.

    Returns None if race/sex are not in MESA categories, or age is outside
    the published 45-84 range.
    """
    if race not in MESA_TABLE or sex not in MESA_TABLE[race]:
        return None
    # Clamp ages outside MESA's published 45-84 range to the nearest endpoint.
    # Patients close to but outside the range still benefit from the closest
    # available reference rather than getting no percentile at all.
    age = max(AGE_MIN, min(AGE_MAX, age))
    by_age = MESA_TABLE[race][sex]
    midpoints = sorted(by_age.keys())  # [50, 60, 70, 80]
    if age <= midpoints[0]:
        return list(by_age[midpoints[0]])
    if age >= midpoints[-1]:
        return list(by_age[midpoints[-1]])
    for i in range(len(midpoints) - 1):
        a0, a1 = midpoints[i], midpoints[i + 1]
        if a0 <= age <= a1:
            t = (age - a0) / (a1 - a0)
            p0 = by_age[a0]
            p1 = by_age[a1]
            return [p0[j] + t * (p1[j] - p0[j]) for j in range(4)]
    return None  # unreachable, but keeps the type checker happy


def percentile_bucket(score: float, age: float, sex: str, race: str) -> str | None:
    """Classify the patient's CAC score into a MESA percentile bucket.

    Returns one of "<25", "25-50", "50-75", "75-90", ">90", or None if
    demographics are missing or out of MESA's reference range.

    A score exactly equal to a published threshold falls into the LOWER
    bucket (e.g. score == p50 -> "25-50"), which is the conservative
    interpretation when the threshold is 0 (common in low-risk groups).
    """
    thr = percentile_thresholds(age, sex, race)
    if thr is None:
        return None
    p25, p50, p75, p90 = thr
    if score <= p25:
        return "<25"
    if score <= p50:
        return "25-50"
    if score <= p75:
        return "50-75"
    if score <= p90:
        return "75-90"
    return ">90"
