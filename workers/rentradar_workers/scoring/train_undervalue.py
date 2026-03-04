#!/usr/bin/env python3
"""Training script for undervalue scoring model.

Generates synthetic training data from comp statistics and trains a
GradientBoostingRegressor. Run standalone:

    python -m rentradar_workers.scoring.train_undervalue
"""

from __future__ import annotations

import logging

import numpy as np

from rentradar_workers.scoring.undervalue import FEATURE_NAMES, train_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def generate_synthetic_data(n_samples: int = 5000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data based on NYC rental market heuristics.

    Features: price_vs_comp_median, price_vs_comp_p25, sqft_ppsf_ratio,
              days_on_market, source_count, bedrooms, has_sqft
    Target: undervalue score (0-100)
    """
    rng = np.random.default_rng(seed)

    X = np.zeros((n_samples, len(FEATURE_NAMES)))
    y = np.zeros(n_samples)

    for i in range(n_samples):
        # Price vs comp median: 0.5 (very underpriced) to 1.5 (overpriced)
        price_vs_median = rng.uniform(0.5, 1.5)
        price_vs_p25 = price_vs_median * rng.uniform(0.9, 1.3)
        ppsf_ratio = rng.choice([0.0, rng.uniform(0.5, 1.5)], p=[0.3, 0.7])
        dom = rng.integers(0, 90)
        sources = rng.integers(1, 5)
        bedrooms = rng.integers(0, 5)
        has_sqft = 1.0 if ppsf_ratio > 0 else 0.0

        X[i] = [price_vs_median, price_vs_p25, ppsf_ratio, dom, sources, bedrooms, has_sqft]

        # Target: lower price_vs_median = higher undervalue score
        base = max(0, (1.0 - price_vs_median) * 150)
        ppsf_bonus = max(0, (1.0 - ppsf_ratio) * 20) if ppsf_ratio > 0 else 0
        dom_penalty = max(0, (dom - 30) * 0.3) if dom > 30 else 0
        source_bonus = (sources - 1) * 3
        noise = rng.normal(0, 5)

        y[i] = np.clip(base + ppsf_bonus - dom_penalty + source_bonus + noise, 0, 100)

    return X, y


def main() -> None:
    log.info("Generating synthetic training data...")
    X, y = generate_synthetic_data()
    log.info("Training undervalue model on %d samples, %d features", X.shape[0], X.shape[1])

    results = train_model(X, y)
    log.info("Training complete:")
    log.info("  R² (train): %.4f", results["train_score"])
    log.info("  R² (test):  %.4f", results["test_score"])
    log.info("  Model saved to: %s", results["model_path"])


if __name__ == "__main__":
    main()
