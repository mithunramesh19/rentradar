#!/usr/bin/env python3
"""Training script for rent-stabilization prediction model.

Generates synthetic training data based on NYC RS rules and trains a
RandomForestClassifier. Run standalone:

    python -m rentradar_workers.scoring.train_rent_stabilized
"""

from __future__ import annotations

import logging

import numpy as np

from rentradar_workers.scoring.rent_stabilized import FEATURE_NAMES, train_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def generate_synthetic_data(n_samples: int = 5000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data based on NYC rent stabilization rules.

    Features: hcr_match, building_age, unit_count, has_tax_abatement,
              borough_manhattan, zip_rs_density
    Target: binary (1 = rent-stabilized, 0 = not)
    """
    rng = np.random.default_rng(seed)

    X = np.zeros((n_samples, len(FEATURE_NAMES)))
    y = np.zeros(n_samples, dtype=int)

    for i in range(n_samples):
        hcr_match = rng.choice([0.0, 1.0], p=[0.7, 0.3])
        building_age = rng.integers(0, 120)
        unit_count = rng.choice([0, rng.integers(1, 200)], p=[0.2, 0.8])
        has_tax = rng.choice([0.0, 1.0], p=[0.8, 0.2])
        manhattan = rng.choice([0.0, 1.0], p=[0.6, 0.4])
        zip_density = rng.uniform(0, 0.8)

        X[i] = [hcr_match, building_age, unit_count, has_tax, manhattan, zip_density]

        # Label based on NYC RS rules + noise
        construction_year = 2024 - building_age
        prob = 0.0

        if hcr_match:
            prob = 0.95
        else:
            if construction_year < 1974 and unit_count >= 6:
                prob = 0.70
            elif construction_year < 1974:
                prob = 0.30
            elif unit_count >= 6:
                prob = 0.15

            if has_tax:
                prob = min(prob + 0.25, 0.95)
            if manhattan:
                prob = min(prob + 0.05, 0.95)
            prob = min(prob + zip_density * 0.1, 0.95)

        y[i] = 1 if rng.random() < prob else 0

    return X, y


def main() -> None:
    log.info("Generating synthetic training data...")
    X, y = generate_synthetic_data()
    pos_rate = y.mean()
    log.info("Training RS model on %d samples (%0.1f%% positive)", len(y), pos_rate * 100)

    results = train_model(X, y)
    log.info("Training complete:")
    log.info("  Accuracy (train): %.4f", results["train_accuracy"])
    log.info("  Accuracy (test):  %.4f", results["test_accuracy"])
    log.info("  Feature importances: %s", results["feature_importances"])
    log.info("  Model saved to: %s", results["model_path"])


if __name__ == "__main__":
    main()
