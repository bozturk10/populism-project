"""Reusable helpers for weighted country-adjusted binary-outcome models."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy.stats import f, t


def inverse_logit(values: np.ndarray) -> np.ndarray:
    """Return numerically stable inverse-logit probabilities."""
    values = np.asarray(values, dtype=float)
    output = np.empty_like(values)
    positive = values >= 0
    output[positive] = 1 / (1 + np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    output[~positive] = exponential / (1 + exponential)
    return output


def cluster_wald_summary(
    estimate: float, standard_error: float, clusters: int, level: float = 0.95
) -> dict[str, float]:
    """Summarize an estimate using a cluster-count t reference distribution."""
    degrees_freedom = clusters - 1
    critical = float(t.ppf(1 - (1 - level) / 2, df=degrees_freedom))
    statistic = estimate / standard_error if standard_error > 0 else np.nan
    p_value = float(2 * t.sf(abs(statistic), df=degrees_freedom))
    return {
        "std_error": float(standard_error),
        "conf_low": float(estimate - critical * standard_error),
        "conf_high": float(estimate + critical * standard_error),
        "statistic": float(statistic),
        "p_value": p_value,
        "df": float(degrees_freedom),
    }


def joint_wald_f(
    result: Any, terms: list[str] | tuple[str, ...], *, clusters: int
) -> dict[str, float]:
    """Test that several coefficients are jointly zero using a cluster-F reference."""
    selected = list(terms)
    missing = set(selected).difference(result.params.index)
    if missing:
        raise KeyError(f"Model does not contain terms: {sorted(missing)}")
    estimates = result.params.loc[selected].to_numpy(dtype=float)
    covariance = result.cov_params().loc[selected, selected].to_numpy(dtype=float)
    rank = int(np.linalg.matrix_rank(covariance))
    if rank != len(selected):
        raise ValueError("Joint-test covariance is rank deficient")
    chi_square = float(estimates @ np.linalg.solve(covariance, estimates))
    statistic = chi_square / len(selected)
    denominator_df = clusters - 1
    return {
        "statistic_f": statistic,
        "numerator_df": float(len(selected)),
        "denominator_df": float(denominator_df),
        "chi_square": chi_square,
        "p_value": float(f.sf(statistic, len(selected), denominator_df)),
    }


def fit_weighted_country_gee(
    formula: str,
    data: pd.DataFrame,
    *,
    weight_column: str | None = "anweight",
    group_column: str = "cntry",
    maxiter: int = 200,
) -> Any:
    """Fit a logistic GEE with independent working correlation by country."""
    weights = None if weight_column is None else data[weight_column]
    model = smf.gee(
        formula,
        groups=group_column,
        data=data,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Independence(),
        weights=weights,
    )
    return model.fit(maxiter=maxiter, cov_type="robust")


def tidy_coefficients(
    result: Any,
    *,
    model: str,
    clusters: int,
    terms: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Return a tidy coefficient table with cluster-count t intervals."""
    rows = []
    selected = result.params if terms is None else result.params.loc[list(terms)]
    covariance = result.cov_params()
    for term, estimate in selected.items():
        variance = float(covariance.loc[term, term])
        standard_error = float(np.sqrt(variance)) if variance >= 0 else np.nan
        summary = cluster_wald_summary(
            float(estimate), standard_error, clusters
        )
        rows.append(
            {
                "model": model,
                "term": term,
                "estimate_log_odds": float(estimate),
                **summary,
                "odds_ratio": float(np.exp(estimate)) if estimate < 709 else np.inf,
                "odds_ratio_low": float(np.exp(summary["conf_low"]))
                if summary["conf_low"] < 709
                else np.inf,
                "odds_ratio_high": float(np.exp(summary["conf_high"]))
                if summary["conf_high"] < 709
                else np.inf,
            }
        )
    return pd.DataFrame(rows)


def average_marginal_effect_arrays(
    params: np.ndarray,
    covariance: np.ndarray,
    exog: np.ndarray,
    variable_index: int,
    weights: np.ndarray,
    *,
    clusters: int,
) -> dict[str, float]:
    """Compute a weighted continuous-variable AME and delta-method uncertainty."""
    params = np.asarray(params, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    exog = np.asarray(exog, dtype=float)
    weights = np.asarray(weights, dtype=float)
    probability = inverse_logit(exog @ params)
    slope = probability * (1 - probability)
    beta = params[variable_index]
    estimate = float(beta * np.average(slope, weights=weights))
    slope_gradient = slope * (1 - 2 * probability)
    mean_gradient = np.average(
        slope_gradient[:, None] * exog, axis=0, weights=weights
    )
    gradient = beta * mean_gradient
    gradient[variable_index] += np.average(slope, weights=weights)
    variance = float(gradient @ covariance @ gradient)
    standard_error = float(np.sqrt(max(variance, 0)))
    return {
        "estimate": estimate,
        **cluster_wald_summary(estimate, standard_error, clusters),
    }


def average_marginal_effect(
    result: Any,
    variable: str,
    weights: pd.Series | np.ndarray,
    *,
    clusters: int,
) -> dict[str, float]:
    """Compute the weighted AME for one continuous term in a fitted model."""
    names = list(result.model.exog_names)
    if variable not in names:
        raise KeyError(f"Model does not contain continuous term {variable!r}")
    return average_marginal_effect_arrays(
        result.params.to_numpy(),
        result.cov_params().to_numpy(),
        result.model.exog,
        names.index(variable),
        np.asarray(weights, dtype=float),
        clusters=clusters,
    )


def average_probability_arrays(
    params: np.ndarray,
    covariance: np.ndarray,
    exog: np.ndarray,
    weights: np.ndarray,
    *,
    clusters: int,
) -> dict[str, float]:
    """Compute an average predicted probability and delta-method uncertainty."""
    params = np.asarray(params, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    exog = np.asarray(exog, dtype=float)
    weights = np.asarray(weights, dtype=float)
    probability = inverse_logit(exog @ params)
    estimate = float(np.average(probability, weights=weights))
    gradient = np.average(
        (probability * (1 - probability))[:, None] * exog,
        axis=0,
        weights=weights,
    )
    variance = float(gradient @ covariance @ gradient)
    standard_error = float(np.sqrt(max(variance, 0)))
    return {
        "estimate": estimate,
        **cluster_wald_summary(estimate, standard_error, clusters),
    }


def counterfactual_average_probability(
    result: Any,
    new_data: pd.DataFrame,
    weights: pd.Series | np.ndarray,
    *,
    clusters: int,
) -> dict[str, float]:
    """Average counterfactual predictions over an observed covariate distribution."""
    design_info = result.model.data.design_info
    exog = np.asarray(build_design_matrices([design_info], new_data)[0])
    return average_probability_arrays(
        result.params.to_numpy(),
        result.cov_params().to_numpy(),
        exog,
        np.asarray(weights, dtype=float),
        clusters=clusters,
    )
