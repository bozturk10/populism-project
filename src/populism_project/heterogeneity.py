"""Helpers for country-effect multiplicity and random-effects synthesis."""

from __future__ import annotations

import numpy as np
from scipy.stats import t


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Return Benjamini-Hochberg adjusted p-values in original order."""
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0, 1)
    return output


def random_effects_meta(
    estimates: np.ndarray, variances: np.ndarray
) -> dict[str, float]:
    """DerSimonian-Laird random-effects synthesis with heterogeneity statistics."""
    effects = np.asarray(estimates, dtype=float)
    variance = np.asarray(variances, dtype=float)
    valid = np.isfinite(effects) & np.isfinite(variance) & (variance > 0)
    effects, variance = effects[valid], variance[valid]
    if len(effects) < 2:
        raise ValueError("Random-effects synthesis requires at least two estimates")
    fixed_weights = 1 / variance
    fixed_mean = np.sum(fixed_weights * effects) / np.sum(fixed_weights)
    q = float(np.sum(fixed_weights * (effects - fixed_mean) ** 2))
    degrees_freedom = len(effects) - 1
    c_value = np.sum(fixed_weights) - np.sum(fixed_weights**2) / np.sum(fixed_weights)
    tau2 = float(max(0, (q - degrees_freedom) / c_value))
    random_weights = 1 / (variance + tau2)
    mean = float(np.sum(random_weights * effects) / np.sum(random_weights))
    standard_error = float(np.sqrt(1 / np.sum(random_weights)))
    critical = float(t.ppf(0.975, df=degrees_freedom))
    prediction_se = float(np.sqrt(tau2 + standard_error**2))
    i2 = float(max(0, (q - degrees_freedom) / q)) if q > 0 else 0.0
    return {
        "k": float(len(effects)),
        "estimate": mean,
        "std_error": standard_error,
        "conf_low": mean - critical * standard_error,
        "conf_high": mean + critical * standard_error,
        "tau2": tau2,
        "i2": i2,
        "q": q,
        "q_df": float(degrees_freedom),
        "prediction_low": mean - critical * prediction_se,
        "prediction_high": mean + critical * prediction_se,
    }


def empirical_bayes_shrink(
    estimates: np.ndarray, variances: np.ndarray, mean: float, tau2: float
) -> np.ndarray:
    """Shrink observed effects toward a supplied random-effects mean."""
    effects = np.asarray(estimates, dtype=float)
    variance = np.asarray(variances, dtype=float)
    if tau2 <= 0:
        return np.full_like(effects, mean)
    reliability = tau2 / (tau2 + variance)
    return mean + reliability * (effects - mean)
