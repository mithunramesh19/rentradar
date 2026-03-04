"""Rent-stabilization prediction — RandomForestClassifier.

Predicts probability that a listing is in a rent-stabilized building.

Features:
- hcr_match: whether address matches HCR database (binary, strongest signal)
- building_age: estimated age from address patterns / tax records
- unit_count: number of units in building (>6 units built before 1974 = likely RS)
- tax_status: tax abatement program presence (421-A, J-51)
- borough_manhattan: is the building in Manhattan
- zip_median_rs_pct: % of RS buildings in the zip code
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "rent_stabilized_model.joblib"

FEATURE_NAMES = [
    "hcr_match",
    "building_age",
    "unit_count",
    "has_tax_abatement",
    "borough_manhattan",
    "zip_rs_density",
]

# Pre-1974 buildings with 6+ units are most likely rent-stabilized
RS_CONSTRUCTION_CUTOFF_YEAR = 1974
RS_MIN_UNITS = 6


@dataclass
class RSFeatures:
    """Feature vector for rent-stabilization prediction."""

    hcr_match: bool  # Direct match in HCR database
    building_age: int  # Estimated years since construction (0 if unknown)
    unit_count: int  # Number of units in building (0 if unknown)
    has_tax_abatement: bool  # 421-A, J-51, etc.
    borough_manhattan: bool  # Manhattan has highest RS density
    zip_rs_density: float  # Fraction of RS buildings in this zip (0-1)

    def to_array(self) -> np.ndarray:
        return np.array([
            1.0 if self.hcr_match else 0.0,
            float(self.building_age),
            float(self.unit_count),
            1.0 if self.has_tax_abatement else 0.0,
            1.0 if self.borough_manhattan else 0.0,
            self.zip_rs_density,
        ]).reshape(1, -1)


def build_features(
    hcr_match: bool,
    building_year: int | None = None,
    unit_count: int | None = None,
    has_tax_abatement: bool = False,
    borough: str | None = None,
    zip_rs_density: float = 0.0,
) -> RSFeatures:
    """Build feature vector from available data."""
    building_age = 0
    if building_year and building_year > 1800:
        building_age = 2024 - building_year

    return RSFeatures(
        hcr_match=hcr_match,
        building_age=building_age,
        unit_count=unit_count or 0,
        has_tax_abatement=has_tax_abatement,
        borough_manhattan=(borough or "").upper() in ("MANHATTAN", "NEW YORK"),
        zip_rs_density=zip_rs_density,
    )


def predict_rs_probability(features: RSFeatures) -> float:
    """Predict probability that a listing is rent-stabilized (0.0 - 1.0).

    Falls back to heuristic rules if no trained model exists.
    """
    if MODEL_PATH.exists():
        return _predict_with_model(features)
    return _heuristic_probability(features)


def _predict_with_model(features: RSFeatures) -> float:
    """Use trained RandomForestClassifier."""
    model = joblib.load(MODEL_PATH)
    X = features.to_array()
    proba = model.predict_proba(X)[0]
    # Return probability of class 1 (rent-stabilized)
    return float(proba[1]) if len(proba) > 1 else float(proba[0])


def _heuristic_probability(features: RSFeatures) -> float:
    """Heuristic fallback using known RS rules.

    NYC rent stabilization applies to:
    - Buildings with 6+ units built before 1974 (Rent Stabilization Law)
    - Buildings receiving J-51 or 421-a tax benefits
    - Direct HCR registration is strongest signal
    """
    if features.hcr_match:
        return 0.95  # Direct HCR match is near-certain

    prob = 0.0

    # Building age: pre-1974 is key threshold
    if features.building_age > 0:
        years_since_construction = features.building_age
        construction_year = 2024 - years_since_construction
        if construction_year < RS_CONSTRUCTION_CUTOFF_YEAR:
            prob += 0.30
            if features.unit_count >= RS_MIN_UNITS:
                prob += 0.25  # 6+ units pre-1974 is the classic RS building

    # Unit count alone is a signal
    if features.unit_count >= RS_MIN_UNITS:
        prob += 0.10

    # Tax abatement is a strong signal
    if features.has_tax_abatement:
        prob += 0.20

    # Manhattan has highest RS density
    if features.borough_manhattan:
        prob += 0.05

    # Zip code density adjusts estimate
    prob += features.zip_rs_density * 0.10

    return round(min(prob, 0.95), 3)


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train a RandomForestClassifier on labeled RS data.

    Args:
        X: Feature matrix (n_samples, 6) matching FEATURE_NAMES
        y: Binary labels (1 = rent-stabilized, 0 = not)
        test_size: Fraction for test split
        random_state: Random seed

    Returns:
        dict with train_accuracy, test_accuracy, model_path, feature_importances
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=random_state,
    )
    model.fit(X_train, y_train)

    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)

    joblib.dump(model, MODEL_PATH)

    importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
    log.info(
        "RS model trained: acc=%.3f (train), acc=%.3f (test). Top features: %s",
        train_acc, test_acc,
        sorted(importances.items(), key=lambda x: -x[1])[:3],
    )

    return {
        "train_accuracy": train_acc,
        "test_accuracy": test_acc,
        "model_path": str(MODEL_PATH),
        "feature_importances": importances,
    }
