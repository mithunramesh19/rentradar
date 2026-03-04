"""Undervalue scoring — GradientBoostingRegressor to detect underpriced listings.

Features:
- price_vs_comp_median: listing price / comp area median (lower = more undervalued)
- price_vs_comp_p25: listing price / comp area 25th percentile
- sqft_ppsf_ratio: listing PPSF / comp area avg PPSF
- days_on_market: normalized DOM (longer = potentially overpriced)
- source_count: number of sources (more = higher confidence)
- bedrooms: bedroom count
- has_sqft: whether sqft is known
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "undervalue_model.joblib"
SCALER_PATH = MODEL_DIR / "undervalue_scaler.joblib"

FEATURE_NAMES = [
    "price_vs_comp_median",
    "price_vs_comp_p25",
    "sqft_ppsf_ratio",
    "days_on_market",
    "source_count",
    "bedrooms",
    "has_sqft",
]


@dataclass
class UndervalueFeatures:
    """Feature vector for undervalue scoring."""

    price_vs_comp_median: float  # listing_price / comp_median
    price_vs_comp_p25: float  # listing_price / comp_p25
    sqft_ppsf_ratio: float  # listing_ppsf / comp_avg_ppsf (0 if unknown)
    days_on_market: float  # normalized to 0-1 range (cap at 90 days)
    source_count: int
    bedrooms: int
    has_sqft: bool

    def to_array(self) -> np.ndarray:
        return np.array([
            self.price_vs_comp_median,
            self.price_vs_comp_p25,
            self.sqft_ppsf_ratio,
            min(self.days_on_market / 90.0, 1.0),
            self.source_count,
            self.bedrooms,
            1.0 if self.has_sqft else 0.0,
        ]).reshape(1, -1)


def build_features(
    price: int,
    comp_median: float,
    comp_p25: float,
    comp_avg_ppsf: float | None,
    sqft: int | None,
    days_on_market: int | None,
    source_count: int,
    bedrooms: int,
) -> UndervalueFeatures:
    """Build feature vector from listing + comp data."""
    price_vs_median = price / comp_median if comp_median > 0 else 1.0
    price_vs_p25 = price / comp_p25 if comp_p25 > 0 else 1.0

    ppsf_ratio = 0.0
    if sqft and sqft > 0 and comp_avg_ppsf and comp_avg_ppsf > 0:
        listing_ppsf = price / sqft
        ppsf_ratio = listing_ppsf / comp_avg_ppsf

    return UndervalueFeatures(
        price_vs_comp_median=price_vs_median,
        price_vs_comp_p25=price_vs_p25,
        sqft_ppsf_ratio=ppsf_ratio,
        days_on_market=float(days_on_market or 0),
        source_count=source_count,
        bedrooms=bedrooms,
        has_sqft=sqft is not None and sqft > 0,
    )


def predict_undervalue(features: UndervalueFeatures) -> float:
    """Predict undervalue score (0-100, higher = more undervalued).

    Returns a heuristic score if no trained model is available.
    """
    if MODEL_PATH.exists() and SCALER_PATH.exists():
        return _predict_with_model(features)
    return _heuristic_score(features)


def _predict_with_model(features: UndervalueFeatures) -> float:
    """Use trained GradientBoostingRegressor model."""
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    X = scaler.transform(features.to_array())
    score = model.predict(X)[0]
    return float(np.clip(score, 0, 100))


def _heuristic_score(features: UndervalueFeatures) -> float:
    """Heuristic fallback when no trained model exists.

    Core logic: how far below the comp median is this listing?
    """
    # Base score from price vs median (a listing at 80% of median gets ~60 score)
    if features.price_vs_comp_median >= 1.0:
        # At or above median — low undervalue
        base = max(0, 30 * (1.0 - (features.price_vs_comp_median - 1.0) / 0.3))
    else:
        # Below median — higher undervalue
        discount = 1.0 - features.price_vs_comp_median
        base = min(30 + discount * 200, 90)

    # PPSF bonus (if we have sqft data)
    ppsf_bonus = 0.0
    if features.sqft_ppsf_ratio > 0:
        if features.sqft_ppsf_ratio < 0.85:
            ppsf_bonus = 10.0
        elif features.sqft_ppsf_ratio < 0.95:
            ppsf_bonus = 5.0

    # DOM penalty (long on market = less likely truly undervalued)
    dom_penalty = 0.0
    if features.days_on_market > 30:
        dom_penalty = min((features.days_on_market - 30) * 0.3, 15)

    # Source confidence boost
    source_bonus = min((features.source_count - 1) * 3, 10)

    score = base + ppsf_bonus - dom_penalty + source_bonus
    return round(max(0, min(score, 100)), 1)


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train a GradientBoostingRegressor on labeled undervalue data.

    Args:
        X: Feature matrix (n_samples, 7) matching FEATURE_NAMES
        y: Target undervalue scores (0-100)
        test_size: Fraction for test split
        random_state: Random seed

    Returns:
        dict with train_score, test_score, model_path
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=random_state,
    )
    model.fit(X_train_scaled, y_train)

    train_score = model.score(X_train_scaled, y_train)
    test_score = model.score(X_test_scaled, y_test)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    log.info(
        "Undervalue model trained: R²=%.3f (train), R²=%.3f (test)",
        train_score, test_score,
    )

    return {
        "train_score": train_score,
        "test_score": test_score,
        "model_path": str(MODEL_PATH),
        "scaler_path": str(SCALER_PATH),
    }
