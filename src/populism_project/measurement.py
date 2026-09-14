"""Measurement construction and diagnostics for Stage 4."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRUST_ITEMS = ["trstprl", "trstplt", "trstprt"]
DOMAIN_TRUST_ITEMS = [
    *TRUST_ITEMS,
    "trstlgl",
    "trstplc",
    "trstep",
    "trstun",
    "trstsci",
    "ppltrst",
]
CORE_ITEMS = [*TRUST_ITEMS, "viepol", "wpestop", "votedir"]
CONTROL_CANDIDATES = ["agea", "gndr", "eisced", "polintr"]
PRIMARY_CONTROLS = ["age_decades_50", "gndr", "eisced_model"]
EXPANDED_CONTROLS = [*PRIMARY_CONTROLS, "polintr"]


def add_measurements(data: pd.DataFrame) -> pd.DataFrame:
    """Add transparent candidate measures without dropping source columns."""
    result = data.copy()
    available_items = [item for item in DOMAIN_TRUST_ITEMS if item in result.columns]
    distrust = 10 - result[available_items]
    distrust.columns = [
        f"distrust_{item.removeprefix('trst').removeprefix('ppltrst')}"
        if item != "ppltrst"
        else "distrust_people"
        for item in available_items
    ]
    result = pd.concat([result, distrust], axis=1)
    political = result[["distrust_prl", "distrust_plt", "distrust_prt"]]
    observed = political.notna().sum(axis=1)
    result["distrust_index_three"] = political.mean(axis=1).where(observed.eq(3))
    result["distrust_index_two_plus"] = political.mean(axis=1).where(observed.ge(2))
    return result


def cronbach_alpha(frame: pd.DataFrame) -> float:
    """Return unstandardized Cronbach's alpha for complete rows."""
    complete = frame.dropna()
    if len(complete) < 2 or frame.shape[1] < 2:
        return float("nan")
    item_variance = complete.var(ddof=1).sum()
    total_variance = complete.sum(axis=1).var(ddof=1)
    if total_variance == 0:
        return float("nan")
    k = frame.shape[1]
    return float(k / (k - 1) * (1 - item_variance / total_variance))


def corrected_item_total_correlations(frame: pd.DataFrame) -> pd.Series:
    """Correlate each item with the sum of the other items on complete rows."""
    complete = frame.dropna()
    if len(complete) < 2 or frame.shape[1] < 2:
        return pd.Series(float("nan"), index=frame.columns, dtype=float)
    return pd.Series(
        {
            column: complete[column].corr(
                complete.drop(columns=column).sum(axis=1)
            )
            for column in complete.columns
        },
        dtype=float,
    )


def alpha_if_item_deleted(frame: pd.DataFrame) -> pd.Series:
    """Return Cronbach's alpha after deleting each item."""
    return pd.Series(
        {
            column: cronbach_alpha(frame.drop(columns=column))
            for column in frame.columns
        },
        dtype=float,
    )


def pca_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Return correlation-matrix PCA eigenvalues, variance shares, and loadings."""
    complete = frame.dropna()
    if len(complete) < 2 or frame.shape[1] < 2:
        return pd.DataFrame()
    correlation = complete.corr().to_numpy()
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    # Correlation matrices can produce tiny negative eigenvalues from roundoff.
    loadings = eigenvectors * np.sqrt(np.clip(eigenvalues, 0, None))
    # Eigenvector signs are arbitrary; orient PC1 so all-positive correlations load up.
    if loadings[:, 0].sum() < 0:
        loadings[:, 0] *= -1
    rows = []
    for component, eigenvalue in enumerate(eigenvalues, start=1):
        row = {
            "component": f"PC{component}",
            "eigenvalue": float(eigenvalue),
            "variance_share": float(eigenvalue / eigenvalues.sum()),
        }
        row.update(
            {
                f"loading_{column}": float(loadings[index, component - 1])
                for index, column in enumerate(frame.columns)
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def add_model_controls(data: pd.DataFrame) -> pd.DataFrame:
    """Add the pre-specified model-control coding without changing source fields."""
    result = data.copy()
    result["age_decades_50"] = (result["agea"] - 50) / 10
    result["eisced_model"] = result["eisced"].where(result["eisced"].between(1, 7))
    return result


def effective_sample_size(weights: pd.Series) -> float:
    """Return Kish's effective sample size for positive observed weights."""
    values = weights.dropna()
    values = values[values > 0].astype(float)
    if values.empty:
        return float("nan")
    return float(values.sum() ** 2 / values.pow(2).sum())


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def weighted_sd(values: pd.Series, weights: pd.Series) -> float:
    """Return the descriptive population SD under positive observed weights."""
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    observed = values[valid].astype(float)
    observed_weights = weights[valid].astype(float)
    mean = np.average(observed, weights=observed_weights)
    variance = np.average((observed - mean) ** 2, weights=observed_weights)
    return float(np.sqrt(variance))
