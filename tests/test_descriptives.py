import numpy as np
import pandas as pd

from populism_project.descriptives import (
    descriptive_stats,
    difference_stats,
    score_band_shares,
)


def test_descriptive_stats_equal_weights_match_known_mean_and_effective_n():
    values = pd.Series([1.0, 2.0, 3.0, np.nan])
    result = descriptive_stats(values, pd.Series([1.0, 1.0, 1.0, 1.0]))
    assert result["n"] == 3
    assert result["effective_n"] == 3.0
    assert result["mean"] == 2.0


def test_difference_stats_uses_first_minus_second_direction():
    first = descriptive_stats(pd.Series([3.0, 4.0, 5.0]))
    second = descriptive_stats(pd.Series([1.0, 2.0, 3.0]))
    result = difference_stats(first, second)
    assert result["difference"] == 2.0
    assert result["ci_low"] < result["difference"] < result["ci_high"]


def test_score_band_shares_are_exhaustive_and_weighted():
    result = score_band_shares(
        pd.Series([0.0, 5.0, 10.0]), pd.Series([1.0, 1.0, 2.0])
    )
    assert result["n"].sum() == 3
    assert np.isclose(result["share"].sum(), 1.0)
    assert result.loc[result["score_band"].eq("8-10"), "share"].item() == 0.5
