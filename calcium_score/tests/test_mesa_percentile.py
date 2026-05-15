"""Unit tests for the MESA percentile module (McClelland 2006, Table 2)."""

from __future__ import annotations

import pytest

from calcium_score.mesa_percentile import (
    MESA_TABLE,
    parse_dicom_age_years,
    percentile_bucket,
    percentile_thresholds,
)


class TestParseDicomAge:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("045Y", 45.0),
            ("084Y", 84.0),
            ("012M", 1.0),
            ("026W", 0.5),
            ("365D", 1.0),
        ],
    )
    def test_units(self, raw, expected):
        assert parse_dicom_age_years(raw) == pytest.approx(expected, rel=1e-3)

    def test_empty_returns_none(self):
        assert parse_dicom_age_years("") is None

    def test_too_short_returns_none(self):
        assert parse_dicom_age_years("4Y") is None

    def test_non_numeric_returns_none(self):
        assert parse_dicom_age_years("ABCY") is None


class TestPercentileThresholdsExactMidpoints:
    @pytest.mark.parametrize(
        "age,sex,race,expected",
        [
            (50, "M", "white", [0, 0, 22, 110]),
            (60, "M", "white", [0, 28, 155, 452]),
            (70, "M", "white", [21, 145, 540, 1345]),
            (80, "M", "white", [103, 385, 1200, 2933]),
            (50, "F", "white", [0, 0, 0, 8]),
            (60, "F", "white", [0, 0, 16, 102]),
            (70, "F", "white", [0, 13, 119, 391]),
            (80, "F", "white", [20, 106, 370, 921]),
            (50, "M", "chinese", [0, 0, 14, 89]),
            (80, "M", "chinese", [11, 81, 305, 769]),
            (60, "F", "black", [0, 0, 5, 74]),
            (70, "M", "hispanic", [1, 56, 247, 666]),
        ],
    )
    def test_match_published(self, age, sex, race, expected):
        assert percentile_thresholds(age, sex, race) == expected


class TestPercentileThresholdsInterpolation:
    def test_midway_between_50_and_60(self):
        # age 55, male white: p90 should be halfway between 110 and 452
        thr = percentile_thresholds(55, "M", "white")
        assert thr is not None
        assert thr[3] == pytest.approx((110 + 452) / 2)
        # p75 halfway between 22 and 155
        assert thr[2] == pytest.approx((22 + 155) / 2)

    def test_clamps_below_50(self):
        # age 45 should give the same thresholds as age 50 (clamp to endpoint)
        assert percentile_thresholds(45, "M", "white") == percentile_thresholds(50, "M", "white")

    def test_clamps_above_80(self):
        assert percentile_thresholds(84, "F", "white") == percentile_thresholds(80, "F", "white")

    def test_below_min_returns_none(self):
        assert percentile_thresholds(40, "M", "white") is None

    def test_above_max_returns_none(self):
        assert percentile_thresholds(90, "M", "white") is None

    def test_unknown_race_returns_none(self):
        assert percentile_thresholds(60, "M", "indigenous") is None

    def test_unknown_sex_returns_none(self):
        assert percentile_thresholds(60, "X", "white") is None


class TestPercentileBucket:
    def test_score_zero_below_25(self):
        # White female age 50: p25=p50=p75=0, p90=8 -> score 0 = "<25"
        assert percentile_bucket(0, 50, "F", "white") == "<25"

    def test_score_equal_to_threshold_goes_to_lower_bucket(self):
        # White male age 60: thresholds [0, 28, 155, 452]
        # score == p50 (28) -> falls into 25-50
        assert percentile_bucket(28, 60, "M", "white") == "25-50"
        # score == p75 (155) -> 50-75
        assert percentile_bucket(155, 60, "M", "white") == "50-75"

    def test_above_p90(self):
        # White male age 60: p90 = 452, score 1000 -> ">90"
        assert percentile_bucket(1000, 60, "M", "white") == ">90"

    def test_below_p25(self):
        # White male age 70: p25 = 21, score 10 -> "<25"
        assert percentile_bucket(10, 70, "M", "white") == "<25"

    def test_between_p25_and_p50(self):
        # White male age 70: p25=21, p50=145, score 100 -> "25-50"
        assert percentile_bucket(100, 70, "M", "white") == "25-50"

    def test_between_p75_and_p90(self):
        # White male age 70: p75=540, p90=1345, score 800 -> "75-90"
        assert percentile_bucket(800, 70, "M", "white") == "75-90"

    def test_returns_none_out_of_range(self):
        assert percentile_bucket(50, 40, "M", "white") is None
        assert percentile_bucket(50, 60, "M", "unknown") is None


class TestTableStructure:
    def test_all_four_races(self):
        assert set(MESA_TABLE.keys()) == {"white", "chinese", "black", "hispanic"}

    def test_both_sexes(self):
        for race in MESA_TABLE:
            assert set(MESA_TABLE[race].keys()) == {"M", "F"}

    def test_four_age_midpoints(self):
        for race in MESA_TABLE:
            for sex in MESA_TABLE[race]:
                assert set(MESA_TABLE[race][sex].keys()) == {50, 60, 70, 80}

    def test_thresholds_monotonic(self):
        # Within any cell, p25 <= p50 <= p75 <= p90.
        for race, by_sex in MESA_TABLE.items():
            for sex, by_age in by_sex.items():
                for age, thrs in by_age.items():
                    assert thrs[0] <= thrs[1] <= thrs[2] <= thrs[3], (
                        f"non-monotonic at {race}/{sex}/{age}: {thrs}"
                    )

    def test_thresholds_nondecreasing_with_age(self):
        # For any race/sex, the 90th percentile should rise (or stay) with age.
        for race, by_sex in MESA_TABLE.items():
            for sex, by_age in by_sex.items():
                ages = sorted(by_age.keys())
                p90s = [by_age[a][3] for a in ages]
                assert all(p90s[i] <= p90s[i + 1] for i in range(len(p90s) - 1)), (
                    f"p90 not non-decreasing for {race}/{sex}: {p90s}"
                )
