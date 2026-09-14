import numpy as np
import pandas as pd

from populism_project.measurement import (
    add_measurements,
    add_model_controls,
    alpha_if_item_deleted,
    corrected_item_total_correlations,
    cronbach_alpha,
    effective_sample_size,
    pca_summary,
    weighted_sd,
)


def test_add_measurements_preserves_sources_and_applies_completeness_rules():
    source = pd.DataFrame(
        {"trstprl": [0.0, 2.0], "trstplt": [5.0, np.nan], "trstprt": [10.0, 6.0]}
    )
    result = add_measurements(source)
    assert result.loc[0, "distrust_index_three"] == 5.0
    assert pd.isna(result.loc[1, "distrust_index_three"])
    assert result.loc[1, "distrust_index_two_plus"] == 6.0
    assert result.loc[0, "trstprl"] == 0.0


def test_reliability_and_effective_sample_size_have_known_values():
    items = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0], "c": [1.0, 2.0, 3.0]}
    )
    assert cronbach_alpha(items) == 1.0
    assert effective_sample_size(pd.Series([1.0, 1.0, 1.0])) == 3.0
    assert np.isclose(
        weighted_sd(pd.Series([1.0, 2.0, 3.0]), pd.Series([1.0, 1.0, 1.0])),
        np.sqrt(2 / 3),
    )


def test_item_diagnostics_and_pca_have_known_perfect_scale_values():
    items = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0], "c": [1.0, 2.0, 3.0]}
    )
    assert corrected_item_total_correlations(items).eq(1.0).all()
    assert alpha_if_item_deleted(items).eq(1.0).all()
    pca = pca_summary(items)
    assert np.isclose(pca.loc[0, "eigenvalue"], 3.0)
    assert np.isclose(pca.loc[0, "variance_share"], 1.0)


def test_add_model_controls_scales_age_and_excludes_unharmonized_education():
    source = pd.DataFrame(
        {"agea": [40.0, 50.0], "eisced": [4.0, 55.0], "gndr": [1.0, 2.0]}
    )
    result = add_model_controls(source)
    assert result["age_decades_50"].tolist() == [-1.0, 0.0]
    assert result.loc[0, "eisced_model"] == 4.0
    assert pd.isna(result.loc[1, "eisced_model"])
    assert result.loc[1, "eisced"] == 55.0
