import numpy as np

from populism_project.modeling import (
    average_marginal_effect_arrays,
    average_probability_arrays,
    cluster_wald_summary,
    inverse_logit,
    joint_wald_f,
)


def test_inverse_logit_is_stable_at_extreme_values():
    result = inverse_logit(np.array([-1000.0, 0.0, 1000.0]))

    assert result[0] == 0.0
    assert result[1] == 0.5
    assert result[2] == 1.0


def test_cluster_wald_summary_uses_clusters_minus_one_degrees_freedom():
    result = cluster_wald_summary(0.2, 0.1, clusters=23)

    assert result["df"] == 22
    assert result["conf_low"] < 0.0 < result["conf_high"]
    assert 0.05 < result["p_value"] < 0.1


def test_average_probability_delta_method_matches_intercept_only_case():
    result = average_probability_arrays(
        params=np.array([0.0]),
        covariance=np.array([[0.04]]),
        exog=np.ones((3, 1)),
        weights=np.array([1.0, 2.0, 1.0]),
        clusters=23,
    )

    assert result["estimate"] == 0.5
    assert np.isclose(result["std_error"], 0.05)


def test_average_marginal_effect_matches_direct_logit_derivative():
    exog = np.array([[1.0, 0.0], [1.0, 1.0]])
    params = np.array([0.0, 0.4])
    probabilities = inverse_logit(exog @ params)
    expected = 0.4 * np.mean(probabilities * (1 - probabilities))
    result = average_marginal_effect_arrays(
        params=params,
        covariance=np.eye(2) * 0.01,
        exog=exog,
        variable_index=1,
        weights=np.ones(2),
        clusters=23,
    )

    assert np.isclose(result["estimate"], expected)
    assert result["std_error"] > 0


def test_joint_wald_f_uses_cluster_degrees_of_freedom():
    class Result:
        params = __import__("pandas").Series({"a": 0.2, "b": 0.4})

        @staticmethod
        def cov_params():
            return __import__("pandas").DataFrame(
                [[0.01, 0.0], [0.0, 0.04]], index=["a", "b"], columns=["a", "b"]
            )

    summary = joint_wald_f(Result(), ["a", "b"], clusters=23)

    assert summary["numerator_df"] == 2
    assert summary["denominator_df"] == 22
    assert np.isclose(summary["statistic_f"], 4.0)
    assert 0 < summary["p_value"] < 0.05
