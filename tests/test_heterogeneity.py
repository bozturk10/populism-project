import numpy as np

from populism_project.heterogeneity import (
    benjamini_hochberg,
    empirical_bayes_shrink,
    random_effects_meta,
)


def test_benjamini_hochberg_preserves_order_and_monotonic_ranks():
    result = benjamini_hochberg(np.array([0.04, 0.001, 0.03]))

    assert np.allclose(result, [0.04, 0.003, 0.04])


def test_random_effects_meta_reports_positive_heterogeneity():
    result = random_effects_meta(
        np.array([-0.2, 0.1, 0.4]), np.array([0.01, 0.01, 0.01])
    )

    assert result["k"] == 3
    assert result["tau2"] > 0
    assert result["prediction_low"] < result["estimate"] < result["prediction_high"]


def test_empirical_bayes_estimates_fall_between_observation_and_mean():
    observed = np.array([-1.0, 1.0])
    result = empirical_bayes_shrink(observed, np.array([1.0, 1.0]), 0.0, 0.25)

    assert np.all(np.abs(result) < np.abs(observed))
