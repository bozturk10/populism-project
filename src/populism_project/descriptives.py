"""Reusable descriptive summaries for Stage 5."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from populism_project.measurement import effective_sample_size, weighted_sd

Z_95 = 1.959963984540054


def descriptive_stats(
    values: pd.Series, weights: pd.Series | None = None
) -> dict[str, float | int]:
    """Return a mean and explicitly approximate 95% descriptive interval."""
    if weights is None:
        observed = values.dropna().astype(float)
        n = len(observed)
        mean = float(observed.mean()) if n else float("nan")
        sd = float(observed.std(ddof=1)) if n > 1 else float("nan")
        effective_n = float(n)
    else:
        valid = values.notna() & weights.notna() & weights.gt(0)
        observed = values[valid].astype(float)
        observed_weights = weights[valid].astype(float)
        n = len(observed)
        mean = (
            float(np.average(observed, weights=observed_weights))
            if n
            else float("nan")
        )
        sd = weighted_sd(observed, observed_weights)
        effective_n = effective_sample_size(observed_weights)
    se = (
        sd / math.sqrt(effective_n)
        if effective_n > 1 and not math.isnan(sd)
        else float("nan")
    )
    return {
        "n": n,
        "effective_n": effective_n,
        "mean": mean,
        "sd": sd,
        "se": se,
        "ci_low": mean - Z_95 * se,
        "ci_high": mean + Z_95 * se,
    }


def difference_stats(
    first: dict[str, float | int], second: dict[str, float | int]
) -> dict[str, float]:
    """Return first-minus-second mean difference and an approximate interval."""
    difference = float(first["mean"]) - float(second["mean"])
    se = math.sqrt(float(first["se"]) ** 2 + float(second["se"]) ** 2)
    return {
        "difference": difference,
        "se": se,
        "ci_low": difference - Z_95 * se,
        "ci_high": difference + Z_95 * se,
    }


def score_band_shares(
    values: pd.Series, weights: pd.Series | None = None
) -> pd.DataFrame:
    """Return shares in descriptive 0-3, 4-7, and 8-10 score bands."""
    valid = values.notna()
    if weights is not None:
        valid &= weights.notna() & weights.gt(0)
        observed_weights = weights[valid].astype(float)
    else:
        observed_weights = pd.Series(1.0, index=values.index[valid])
    observed = values[valid]
    total = observed_weights.sum()
    bands = {
        "0-3": observed.le(3),
        "4-7": observed.gt(3) & observed.lt(8),
        "8-10": observed.ge(8),
    }
    return pd.DataFrame(
        [
            {
                "score_band": label,
                "n": int(mask.sum()),
                "share": float(observed_weights[mask].sum() / total),
            }
            for label, mask in bands.items()
        ]
    )
