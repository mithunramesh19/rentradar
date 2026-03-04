"""Unit tests for scoring modules: comps, undervalue, rent-stabilized, quality."""

import numpy as np
import polars as pl
import pytest


# ── Comp area calculator tests ──────────────────────────────────────────


class TestCompStats:
    def test_aggregate_stats_basic(self):
        from rentradar_workers.scoring.comps import CompStats, _aggregate_stats

        df = pl.DataFrame({
            "price": [2000, 2500, 3000, 3500, 4000],
            "sqft": [500, 600, 700, 800, 900],
        })
        stats = _aggregate_stats(df, "East Village", 1)
        assert stats is not None
        assert stats.neighborhood == "East Village"
        assert stats.bedrooms == 1
        assert stats.median == 3000.0
        assert stats.count == 5
        assert stats.p25 < stats.median < stats.p75
        assert stats.avg_sqft is not None
        assert stats.avg_ppsf is not None

    def test_aggregate_stats_no_sqft(self):
        from rentradar_workers.scoring.comps import _aggregate_stats

        df = pl.DataFrame({
            "price": [2000, 2500, 3000],
            "sqft": [None, None, None],
        })
        stats = _aggregate_stats(df, "SoHo", 0)
        assert stats is not None
        assert stats.avg_sqft is None
        assert stats.avg_ppsf is None

    def test_aggregate_stats_empty(self):
        from rentradar_workers.scoring.comps import _aggregate_stats

        df = pl.DataFrame({"price": [], "sqft": []}).cast({"price": pl.Int64, "sqft": pl.Int64})
        stats = _aggregate_stats(df, "NoHo", 2)
        assert stats is None

    def test_cache_key_format(self):
        from rentradar_workers.scoring.comps import _cache_key

        key = _cache_key("East Village", 1)
        assert key == "rentradar:comps:East Village:1"


# ── Quality score tests ─────────────────────────────────────────────────


class TestQualityScore:
    def test_minimal_quality(self):
        from rentradar_workers.scoring.quality import compute_quality_score

        result = compute_quality_score(source_count=0)
        assert result.total == 0.0

    def test_default_source_gives_some_score(self):
        from rentradar_workers.scoring.quality import compute_quality_score

        result = compute_quality_score()  # source_count defaults to 1
        assert result.total == 6.0  # 40 * 0.15 weight

    def test_perfect_quality(self):
        from rentradar_workers.scoring.quality import compute_quality_score

        result = compute_quality_score(
            photo_count=15,
            has_sqft=True,
            sqft=800,
            description=(
                "Stunning renovated apartment with hardwood floors and stainless steel "
                "appliances. Natural light floods the space through oversized windows. "
                "In-unit laundry, dishwasher, and central air. Building features doorman, "
                "gym, and rooftop terrace. Pet-friendly with elevator access. "
                "Walk-in closet and ample storage. Marble bathroom with granite countertops. "
                "Steps from subway and parks. " * 3
            ),
            amenities=["laundry", "dishwasher", "doorman", "gym", "elevator",
                        "roof", "storage", "parking", "ac", "hw_floors",
                        "balcony", "pets", "concierge", "pool", "garden"],
            source_count=4,
        )
        assert result.total >= 90.0  # Near perfect

    def test_photos_scoring(self):
        from rentradar_workers.scoring.quality import _score_photos

        assert _score_photos(0) == 0.0
        assert 0 < _score_photos(3) < _score_photos(7) < _score_photos(15)
        assert _score_photos(15) == 100.0

    def test_description_quality(self):
        from rentradar_workers.scoring.quality import _score_description

        assert _score_description(None) == 0.0
        assert _score_description("") == 0.0
        # "short" is below min length for length score but gets quality points
        # for not being all caps
        assert _score_description("short") == 10.0
        long_desc = "Beautiful renovated apartment with hardwood floors. " * 20
        assert _score_description(long_desc) > 50

    def test_sources_scoring(self):
        from rentradar_workers.scoring.quality import _score_sources

        assert _score_sources(0) == 0.0
        assert _score_sources(1) == 40.0
        assert _score_sources(2) == 70.0
        assert _score_sources(4) == 100.0

    def test_score_listing_dict(self):
        from rentradar_workers.scoring.quality import score_listing

        score = score_listing({
            "photo_count": 5,
            "sqft": 750,
            "description": "Nice apartment with elevator and laundry. Renovated kitchen.",
            "amenities": ["laundry", "elevator", "dishwasher", "ac", "hw_floors"],
            "source_count": 2,
        })
        assert 0 <= score <= 100


# ── Undervalue scoring tests ────────────────────────────────────────────


class TestUndervalueScore:
    def test_build_features(self):
        from rentradar_workers.scoring.undervalue import build_features

        f = build_features(
            price=2000, comp_median=2500, comp_p25=2200,
            comp_avg_ppsf=3.5, sqft=600, days_on_market=10,
            source_count=2, bedrooms=1,
        )
        assert f.price_vs_comp_median == pytest.approx(0.8, abs=0.01)
        assert f.has_sqft is True
        assert f.to_array().shape == (1, 7)

    def test_heuristic_undervalued(self):
        from rentradar_workers.scoring.undervalue import UndervalueFeatures, _heuristic_score

        # Well below median → high score
        f = UndervalueFeatures(
            price_vs_comp_median=0.7,
            price_vs_comp_p25=0.8,
            sqft_ppsf_ratio=0.75,
            days_on_market=5,
            source_count=2,
            bedrooms=1,
            has_sqft=True,
        )
        score = _heuristic_score(f)
        assert score > 50

    def test_heuristic_overpriced(self):
        from rentradar_workers.scoring.undervalue import UndervalueFeatures, _heuristic_score

        # Above median → low score
        f = UndervalueFeatures(
            price_vs_comp_median=1.3,
            price_vs_comp_p25=1.5,
            sqft_ppsf_ratio=1.3,
            days_on_market=60,
            source_count=1,
            bedrooms=2,
            has_sqft=True,
        )
        score = _heuristic_score(f)
        assert score < 20

    def test_train_model(self):
        from rentradar_workers.scoring.undervalue import train_model

        rng = np.random.default_rng(42)
        X = rng.random((100, 7))
        y = np.clip(X[:, 0] * 50 + rng.normal(0, 5, 100), 0, 100)

        results = train_model(X, y, test_size=0.3)
        assert results["train_score"] > 0  # Model learned something
        assert "model_path" in results


# ── Rent-stabilization prediction tests ─────────────────────────────────


class TestRentStabilizedPrediction:
    def test_build_features(self):
        from rentradar_workers.scoring.rent_stabilized import build_features

        f = build_features(
            hcr_match=True,
            building_year=1960,
            unit_count=50,
            borough="Manhattan",
        )
        assert f.hcr_match is True
        assert f.building_age == 64
        assert f.borough_manhattan is True
        assert f.to_array().shape == (1, 6)

    def test_heuristic_hcr_match(self):
        from rentradar_workers.scoring.rent_stabilized import RSFeatures, _heuristic_probability

        f = RSFeatures(
            hcr_match=True, building_age=60, unit_count=20,
            has_tax_abatement=False, borough_manhattan=True, zip_rs_density=0.5,
        )
        prob = _heuristic_probability(f)
        assert prob == 0.95  # HCR match = near-certain

    def test_heuristic_pre1974_large(self):
        from rentradar_workers.scoring.rent_stabilized import RSFeatures, _heuristic_probability

        f = RSFeatures(
            hcr_match=False, building_age=60, unit_count=20,
            has_tax_abatement=False, borough_manhattan=True, zip_rs_density=0.3,
        )
        prob = _heuristic_probability(f)
        assert prob > 0.5  # Pre-1974 + 6+ units = likely RS

    def test_heuristic_new_building(self):
        from rentradar_workers.scoring.rent_stabilized import RSFeatures, _heuristic_probability

        f = RSFeatures(
            hcr_match=False, building_age=5, unit_count=10,
            has_tax_abatement=False, borough_manhattan=False, zip_rs_density=0.1,
        )
        prob = _heuristic_probability(f)
        assert prob < 0.3  # New building, no abatement

    def test_train_model(self):
        from rentradar_workers.scoring.rent_stabilized import train_model

        rng = np.random.default_rng(42)
        X = rng.random((200, 6))
        y = (X[:, 0] > 0.5).astype(int)  # Simple rule based on first feature

        results = train_model(X, y, test_size=0.3)
        assert results["train_accuracy"] > 0.5
        assert "feature_importances" in results
