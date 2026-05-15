"""Unit tests for the pure Agatston scoring module."""

from __future__ import annotations

import numpy as np
import pytest

from calcium_score.scoring import (
    HU_THRESHOLD,
    Lesion,
    density_weight,
    filter_small_components,
    grand_total,
    hu_from_raw,
    lesion_score,
    pixel_area_mm2,
    risk_category,
    score_flood_fill,
    score_polygon,
    totals_by_artery,
)


class TestDensityWeight:
    def test_below_threshold_returns_zero(self):
        assert density_weight(129) == 0
        assert density_weight(0) == 0
        assert density_weight(-100) == 0

    def test_threshold_boundary(self):
        assert density_weight(130) == 1

    @pytest.mark.parametrize(
        "hu,expected",
        [
            (130, 1),
            (150, 1),
            (199, 1),
            (200, 2),
            (250, 2),
            (299, 2),
            (300, 3),
            (399, 3),
            (400, 4),
            (450, 4),
            (1000, 4),
        ],
    )
    def test_buckets(self, hu, expected):
        assert density_weight(hu) == expected


class TestLesionScore:
    def test_small_lesion_returns_zero(self):
        # 0.5 mm^2 < 1 mm^2 minimum
        assert lesion_score(0.5, 250) == 0.0

    def test_below_threshold_returns_zero(self):
        assert lesion_score(5.0, 100) == 0.0

    def test_classic_examples(self):
        # 15 mm^2 lesion at 250 HU -> 15 * 2 = 30
        assert lesion_score(15.0, 250) == 30.0
        # 10 mm^2 lesion at 450 HU -> 10 * 4 = 40
        assert lesion_score(10.0, 450) == 40.0

    def test_exactly_one_mm2(self):
        # 1.0 mm^2 should score (boundary, not excluded)
        assert lesion_score(1.0, 150) == 1.0


class TestRiskCategory:
    @pytest.mark.parametrize(
        "total,expected",
        [
            (0, "ausente"),
            (0.1, "mínimo"),
            (9.99, "mínimo"),
            (10, "discreto"),
            (99, "discreto"),
            (100, "moderado"),
            (399, "moderado"),
            (400, "acentuado"),
            (999, "acentuado"),
            (1000, "muito acentuado"),
            (5000, "muito acentuado"),
        ],
    )
    def test_buckets(self, total, expected):
        assert risk_category(total) == expected


class TestScoreFloodFill:
    def test_isolated_block(self):
        # 1 mm per pixel, 5x5 block at HU=250 -> area 25 mm^2, weight 2, score 50
        hu = np.full((20, 20), -1000, dtype=np.float32)
        hu[5:10, 5:10] = 250
        les = score_flood_fill(hu, (7, 7), pixel_area_mm2=1.0, artery="DA", slice_index=3)
        assert les is not None
        assert les.area_mm2 == 25.0
        assert les.max_hu == 250.0
        assert les.score == 50.0
        assert les.artery == "DA"
        assert les.slice_index == 3
        assert les.mask.shape == hu.shape
        assert les.mask.sum() == 25

    def test_seed_below_threshold_returns_none(self):
        hu = np.full((10, 10), -1000, dtype=np.float32)
        hu[5, 5] = 100  # below threshold
        assert score_flood_fill(hu, (5, 5), 1.0, artery="DA", slice_index=0) is None

    def test_seed_out_of_bounds(self):
        hu = np.full((10, 10), 200, dtype=np.float32)
        assert score_flood_fill(hu, (-1, 0), 1.0, artery="DA", slice_index=0) is None
        assert score_flood_fill(hu, (10, 0), 1.0, artery="DA", slice_index=0) is None

    def test_does_not_leak_to_disconnected_region(self):
        hu = np.full((20, 20), -1000, dtype=np.float32)
        hu[2:4, 2:4] = 200  # 2x2 block A
        hu[15:17, 15:17] = 500  # 2x2 block B (disconnected)
        les = score_flood_fill(hu, (2, 2), 1.0, artery="CD", slice_index=0)
        assert les is not None
        # Should only have picked up block A (4 mm^2 at max 200 HU, weight 2)
        assert les.area_mm2 == 4.0
        assert les.max_hu == 200.0
        assert les.score == 8.0

    def test_uses_max_hu_for_weight(self):
        # mixed HU in same connected blob -> weight from peak
        hu = np.full((10, 10), -1000, dtype=np.float32)
        hu[3:6, 3:6] = 200  # 9 pixels at 200 (weight 2 if alone)
        hu[4, 4] = 450  # one pixel at 450 -> raises weight to 4
        les = score_flood_fill(hu, (4, 4), 1.0, artery="DA", slice_index=0)
        assert les is not None
        assert les.area_mm2 == 9.0
        assert les.max_hu == 450.0
        assert les.score == 9.0 * 4

    def test_sub_mm2_lesion_scores_zero(self):
        # pixel area 0.1 mm^2, 5-pixel blob -> 0.5 mm^2 area (below 1 mm^2 minimum)
        hu = np.full((10, 10), -1000, dtype=np.float32)
        hu[2, 2:7] = 200
        les = score_flood_fill(hu, (2, 4), 0.1, artery="DA", slice_index=0)
        assert les is not None
        assert les.area_mm2 == pytest.approx(0.5)
        assert les.score == 0.0


class TestScorePolygon:
    def test_polygon_keeps_only_above_threshold(self):
        hu = np.full((20, 20), 100, dtype=np.float32)  # everywhere below threshold
        hu[5:10, 5:10] = 250  # 5x5 calcified region
        # polygon covers the whole image (almost) -> only the calcified 25 pixels score
        poly = np.array([[1, 1], [18, 1], [18, 18], [1, 18]], dtype=float)
        les = score_polygon(hu, poly, 1.0, artery="Cx", slice_index=0)
        assert les is not None
        assert les.area_mm2 == 25.0
        assert les.max_hu == 250.0
        assert les.score == 50.0

    def test_polygon_with_fewer_than_three_vertices_returns_none(self):
        hu = np.full((10, 10), 300, dtype=np.float32)
        assert score_polygon(hu, np.array([[1, 1], [2, 2]]), 1.0, artery="DA", slice_index=0) is None

    def test_polygon_misses_calcium_returns_none(self):
        hu = np.full((20, 20), -1000, dtype=np.float32)
        hu[15:18, 15:18] = 300
        # polygon in opposite corner
        poly = np.array([[1, 1], [4, 1], [4, 4], [1, 4]], dtype=float)
        assert score_polygon(hu, poly, 1.0, artery="DA", slice_index=0) is None


class TestAggregation:
    def _mk_lesion(self, artery: str, score: float) -> Lesion:
        return Lesion(
            artery=artery,
            slice_index=0,
            area_mm2=score / 2.0 if score else 0.0,
            max_hu=250.0,
            score=score,
            mask=np.zeros((1, 1), dtype=bool),
        )

    def test_totals_by_artery_includes_zero_arteries(self):
        lesions = [self._mk_lesion("DA", 30.0), self._mk_lesion("DA", 10.0), self._mk_lesion("CD", 25.0)]
        totals = totals_by_artery(lesions)
        assert totals == {"TCE": 0.0, "DA": 40.0, "Cx": 0.0, "CD": 25.0, "DP": 0.0}

    def test_grand_total(self):
        lesions = [self._mk_lesion("DA", 30.0), self._mk_lesion("CD", 25.0)]
        assert grand_total(lesions) == 55.0


class TestFilterSmallComponents:
    def test_keeps_only_large_enough_blobs(self):
        # 1 mm/pixel, threshold 1 mm^2 -> blobs need >=1 pixel (no filter)
        # Use 0.5 mm/pixel (0.25 mm^2/pixel) -> min 4 pixels for 1 mm^2
        m = np.zeros((10, 10), dtype=bool)
        m[2:4, 2:4] = True  # 4-pixel blob (1 mm^2 exactly) -> kept
        m[6, 6] = True       # 1-pixel blob (0.25 mm^2) -> dropped
        m[7, 7] = True       # another isolated noise pixel
        out = filter_small_components(m, pixel_area_mm2=0.25)
        assert out[2:4, 2:4].all()
        assert out.sum() == 4  # only the 2x2 blob survives

    def test_no_filter_when_pixel_threshold_is_one(self):
        # If 1 pixel is already >= min_area_mm2, no filtering happens
        m = np.zeros((5, 5), dtype=bool)
        m[2, 2] = True
        out = filter_small_components(m, pixel_area_mm2=2.0)  # min_pixels = 1
        assert out[2, 2]
        assert out.sum() == 1

    def test_empty_mask(self):
        m = np.zeros((5, 5), dtype=bool)
        out = filter_small_components(m, pixel_area_mm2=0.25)
        assert not out.any()

    def test_returns_new_array(self):
        m = np.zeros((5, 5), dtype=bool)
        m[1, 1] = True
        out = filter_small_components(m, pixel_area_mm2=0.25)
        assert out is not m  # caller can mutate independently


class TestHelpers:
    def test_pixel_area(self):
        assert pixel_area_mm2((0.5, 0.5)) == 0.25
        assert pixel_area_mm2([0.4, 0.6]) == pytest.approx(0.24)

    def test_hu_from_raw_default_intercept(self):
        raw = np.array([[0, 1024, 2048]], dtype=np.uint16)
        hu = hu_from_raw(raw)
        np.testing.assert_array_equal(hu, np.array([[-1024.0, 0.0, 1024.0]], dtype=np.float32))

    def test_hu_from_raw_custom(self):
        raw = np.array([[100]], dtype=np.uint16)
        hu = hu_from_raw(raw, rescale_slope=2.0, rescale_intercept=-200.0)
        assert hu[0, 0] == 0.0

    def test_hu_threshold_constant_matches_spec(self):
        assert HU_THRESHOLD == 130
