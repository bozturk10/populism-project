# ruff: noqa: E501
"""Build reproducible Stage 4 measurement and sample diagnostics."""

from __future__ import annotations

import markdown
import matplotlib.pyplot as plt
import pandas as pd

from populism_project.config import ANALYSIS_BASE, ROOT
from populism_project.measurement import (
    CONTROL_CANDIDATES,
    CORE_ITEMS,
    EXPANDED_CONTROLS,
    PRIMARY_CONTROLS,
    add_measurements,
    add_model_controls,
    alpha_if_item_deleted,
    corrected_item_total_correlations,
    cronbach_alpha,
    effective_sample_size,
    pca_summary,
    weighted_mean,
    weighted_sd,
)

REPORTS = ROOT / "outputs" / "reports"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"
MIN_OUTCOME_CELL = 30
WEAK_VIEPOL_SD = 1.75
SEVERE_VIEPOL_SHARE_8_10 = 0.75
SEVERE_VIEPOL_SHARE_10 = 0.50

VARIABLE_LABELS = {
    "trstprl": "trstprl (trust in parliament)",
    "trstplt": "trstplt (trust in politicians)",
    "trstprt": "trstprt (trust in political parties)",
    "viepol": "viepol (ordinary people's views should prevail over political elites)",
    "wpestop": "wpestop (the will of the people cannot be stopped)",
    "agea": "agea (age)",
    "gndr": "gndr (gender)",
    "eisced": "eisced (education level)",
    "mainact": "mainact (main activity; currently unsuitable as coded)",
    "polintr": "polintr (interest in politics)",
    "anweight": "anweight (ESS analysis weight)",
    "mode": "mode (survey data-collection mode)",
}


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    header = "| " + " | ".join(values.columns) + " |"
    divider = "|" + "|".join("---" for _ in values.columns) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in values.to_numpy()]
    return "\n".join([header, divider, *rows])


def validate_input(data: pd.DataFrame) -> None:
    """Fail loudly if canonical Table C no longer matches the reviewed baseline."""
    if len(data) != 59_685 or data["cntry"].nunique() != 31:
        raise ValueError("Table C must contain 59,685 respondents in 31 countries")
    if not data["respondent_key"].is_unique:
        raise ValueError("respondent_key must be unique in Table C")
    eligible = data.loc[data["analysis_eligible"]]
    if len(eligible) != 32_760 or eligible["cntry"].nunique() != 27:
        raise ValueError("Eligible sample must contain 32,760 voters in 27 countries")
    if not set(eligible["voted_populist"].dropna().unique()).issubset({0, 1}):
        raise ValueError("Eligible outcomes must be binary")
    if eligible["anweight"].isna().any() or eligible["anweight"].le(0).any():
        raise ValueError("Eligible analysis weights must be observed and positive")
    for column in CORE_ITEMS:
        observed = eligible[column].dropna()
        if not observed.between(0, 10).all():
            raise ValueError(f"{column} contains values outside 0-10")


def build_tables(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    eligible = add_model_controls(
        add_measurements(data.loc[data["analysis_eligible"]].copy())
    )
    distrust_cols = ["distrust_prl", "distrust_plt", "distrust_prt"]

    complete_items = eligible[distrust_cols].dropna()
    item_totals = corrected_item_total_correlations(eligible[distrust_cols])
    deleted_alphas = alpha_if_item_deleted(eligible[distrust_cols])

    reliability = pd.DataFrame(
        [
            {
                "measure": "Political distrust (3 items)",
                "items": (
                    "Trust in parliament (trstprl); Trust in politicians (trstplt); "
                    "Trust in political parties (trstprt)"
                ),
                "complete_n": int(eligible[distrust_cols].notna().all(axis=1).sum()),
                "cronbach_alpha": cronbach_alpha(eligible[distrust_cols]),
            }
        ]
    )
    reliability_items = pd.DataFrame(
        [
            {
                "item": column,
                "complete_n": len(complete_items),
                "corrected_item_total_correlation": item_totals[column],
                "alpha_if_item_deleted": deleted_alphas[column],
            }
            for column in distrust_cols
        ]
    )
    pca = pca_summary(eligible[distrust_cols])

    item_summary_rows = []
    item_distribution_rows = []
    for column in distrust_cols:
        observed = eligible[column].notna()
        valid_weight = observed & eligible["anweight"].gt(0)
        item_summary_rows.append(
            {
                "item": column,
                "observed_n": int(observed.sum()),
                "missing_n": int((~observed).sum()),
                "missing_share": (~observed).mean(),
                "mean": eligible.loc[observed, column].mean(),
                "sd": eligible.loc[observed, column].std(),
                "weighted_mean": weighted_mean(
                    eligible[column], eligible["anweight"]
                ),
                "share_0": eligible.loc[observed, column].eq(0).mean(),
                "share_10": eligible.loc[observed, column].eq(10).mean(),
            }
        )
        total_weight = eligible.loc[valid_weight, "anweight"].sum()
        for score in range(11):
            score_mask = valid_weight & eligible[column].eq(score)
            item_distribution_rows.append(
                {
                    "item": column,
                    "score": score,
                    "unweighted_n": int(score_mask.sum()),
                    "weighted_share": (
                        eligible.loc[score_mask, "anweight"].sum() / total_weight
                    ),
                }
            )
    item_summary = pd.DataFrame(item_summary_rows)
    item_distributions = pd.DataFrame(item_distribution_rows)
    correlations = (
        eligible[[*distrust_cols, "viepol", "wpestop"]]
        .corr()
        .reset_index(names="variable")
    )
    domain_columns = {
        "distrust_prl": "Parliament (trstprl)",
        "distrust_plt": "Politicians (trstplt)",
        "distrust_prt": "Political parties (trstprt)",
        "distrust_lgl": "Legal system (trstlgl)",
        "distrust_plc": "Police (trstplc)",
        "distrust_ep": "European Parliament (trstep)",
        "distrust_un": "United Nations (trstun)",
        "distrust_sci": "Scientists (trstsci)",
        "distrust_people": "Other people (ppltrst)",
    }
    domain_correlations = (
        eligible[list(domain_columns)]
        .rename(columns=domain_columns)
        .corr()
        .reset_index(names="Institution")
    )

    variables = [*CORE_ITEMS, *CONTROL_CANDIDATES, "anweight", "mode"]
    missingness = pd.DataFrame(
        [
            {
                "variable": column,
                "observed_n": int(eligible[column].notna().sum()),
                "missing_n": int(eligible[column].isna().sum()),
                "missing_share": eligible[column].isna().mean(),
            }
            for column in variables
        ]
    )

    variation_rows = []
    for country, group in eligible.groupby("cntry", sort=True):
        for variable in ["viepol", "wpestop"]:
            observed = group[variable].dropna()
            valid_weight = group[variable].notna() & group["anweight"].gt(0)
            values = group.loc[valid_weight, variable]
            weights_for_variable = group.loc[valid_weight, "anweight"]
            total_weight = weights_for_variable.sum()
            variation_rows.append(
                {
                    "cntry": country,
                    "variable": variable,
                    "n": len(observed),
                    "mean": observed.mean(),
                    "sd": observed.std(),
                    "share_8_10": observed.ge(8).mean(),
                    "share_10": observed.eq(10).mean(),
                    "weighted_mean": weighted_mean(values, weights_for_variable),
                    "weighted_sd": weighted_sd(values, weights_for_variable),
                    "weighted_share_8_10": weights_for_variable[
                        values.ge(8)
                    ].sum()
                    / total_weight,
                    "weighted_share_10": weights_for_variable[
                        values.eq(10)
                    ].sum()
                    / total_weight,
                }
            )
    country_variation = pd.DataFrame(variation_rows)
    viepol_rows = country_variation["variable"].eq("viepol")
    country_variation["weak_sd_flag"] = False
    country_variation["severe_ceiling_flag"] = False
    country_variation.loc[viepol_rows, "weak_sd_flag"] = country_variation.loc[
        viepol_rows, "weighted_sd"
    ].lt(WEAK_VIEPOL_SD)
    country_variation.loc[viepol_rows, "severe_ceiling_flag"] = (
        country_variation.loc[viepol_rows, "weighted_share_8_10"].ge(
            SEVERE_VIEPOL_SHARE_8_10
        )
        | country_variation.loc[viepol_rows, "weighted_share_10"].ge(
            SEVERE_VIEPOL_SHARE_10
        )
    )

    h2_distribution_rows = []
    for variable in ["viepol", "wpestop"]:
        valid = eligible[variable].notna() & eligible["anweight"].gt(0)
        values = eligible.loc[valid, variable]
        weights_for_variable = eligible.loc[valid, "anweight"]
        total_weight = weights_for_variable.sum()
        h2_distribution_rows.append(
            {
                "variable": variable,
                "observed_n": int(valid.sum()),
                "weighted_mean": weighted_mean(values, weights_for_variable),
                "weighted_sd": weighted_sd(values, weights_for_variable),
                "weighted_share_8_10": weights_for_variable[
                    values.ge(8)
                ].sum()
                / total_weight,
                "weighted_share_10": weights_for_variable[
                    values.eq(10)
                ].sum()
                / total_weight,
            }
        )
    h2_distributions = pd.DataFrame(h2_distribution_rows)

    country_reliability_rows = []
    for country, group in eligible.groupby("cntry", sort=True):
        country_complete = group[distrust_cols].dropna()
        country_reliability_rows.append(
            {
                "cntry": country,
                "complete_n": len(country_complete),
                "cronbach_alpha": cronbach_alpha(country_complete),
            }
        )
    country_reliability = pd.DataFrame(country_reliability_rows)
    country_reliability_summary = pd.DataFrame(
        [
            {
                "countries": len(country_reliability),
                "min_alpha": country_reliability["cronbach_alpha"].min(),
                "q1_alpha": country_reliability["cronbach_alpha"].quantile(0.25),
                "median_alpha": country_reliability["cronbach_alpha"].median(),
                "q3_alpha": country_reliability["cronbach_alpha"].quantile(0.75),
                "max_alpha": country_reliability["cronbach_alpha"].max(),
                "countries_alpha_ge_0_70": int(
                    country_reliability["cronbach_alpha"].ge(0.70).sum()
                ),
            }
        ]
    )

    distribution_rows = []
    distribution_measures = {
        "distrust_index_three": (
            "Political distrust index (trstprl + trstplt + trstprt)"
        ),
        "viepol": (
            "viepol (ordinary people's views should prevail over political elites)"
        ),
    }
    for country, group in eligible.groupby("cntry", sort=True):
        for variable, label in distribution_measures.items():
            valid = group[variable].notna() & group["anweight"].gt(0)
            values = group.loc[valid, variable]
            weights = group.loc[valid, "anweight"]
            total_weight = weights.sum()
            bands = {
                "0-3": values.le(3),
                "4-7": values.gt(3) & values.lt(8),
                "8-10": values.ge(8),
            }
            for band, mask in bands.items():
                distribution_rows.append(
                    {
                        "cntry": country,
                        "measure": label,
                        "score_band": band,
                        "weighted_share": weights[mask].sum() / total_weight,
                        "observed_n": int(valid.sum()),
                    }
                )
    country_distributions = pd.DataFrame(distribution_rows)

    sample_masks = [
        ("Classifiable outcome", pd.Series(True, index=eligible.index)),
        (
            "Distrust index: all 3 items",
            eligible["distrust_index_three"].notna(),
        ),
        (
            "Plus viepol",
            eligible["distrust_index_three"].notna() & eligible["viepol"].notna(),
        ),
        (
            "Plus positive anweight",
            eligible["distrust_index_three"].notna()
            & eligible["viepol"].notna()
            & eligible["anweight"].gt(0),
        ),
        (
            "Plus all provisional controls",
            eligible["distrust_index_three"].notna()
            & eligible["viepol"].notna()
            & eligible["anweight"].gt(0)
            & eligible[CONTROL_CANDIDATES].notna().all(axis=1),
        ),
    ]
    flow_rows, previous = [], len(eligible)
    for stage, mask in sample_masks:
        retained = int(mask.sum())
        flow_rows.append(
            {
                "stage": stage,
                "retained": retained,
                "dropped_at_stage": previous - retained,
                "retained_share_of_outcome_sample": retained / len(eligible),
            }
        )
        previous = retained
    sample_flow = pd.DataFrame(flow_rows)

    index_comparison = pd.DataFrame(
        [
            {
                "rule": "All three items",
                "n": int(eligible["distrust_index_three"].notna().sum()),
                "weighted_mean": weighted_mean(
                    eligible["distrust_index_three"], eligible["anweight"]
                ),
            },
            {
                "rule": "At least two items",
                "n": int(eligible["distrust_index_two_plus"].notna().sum()),
                "weighted_mean": weighted_mean(
                    eligible["distrust_index_two_plus"], eligible["anweight"]
                ),
            },
        ]
    )

    sparse = (
        eligible.groupby("cntry")["voted_populist"]
        .agg(classifiable="size", populist="sum")
        .reset_index()
    )
    sparse["non_populist"] = sparse["classifiable"] - sparse["populist"]
    sparse["flag_under_30"] = sparse[["populist", "non_populist"]].min(axis=1).lt(30)

    primary_countries = set(sparse.loc[~sparse["flag_under_30"], "cntry"])
    common_primary = (
        eligible["cntry"].isin(primary_countries)
        & eligible["anweight"].gt(0)
        & eligible[PRIMARY_CONTROLS].notna().all(axis=1)
    )
    model_masks = {
        "H1 primary: distrust + primary controls": common_primary
        & eligible["distrust_index_three"].notna(),
        "H2 primary: H1 + viepol + primary controls": common_primary
        & eligible["distrust_index_three"].notna()
        & eligible["viepol"].notna(),
        "H2 expanded: primary + polintr": common_primary
        & eligible["distrust_index_three"].notna()
        & eligible["viepol"].notna()
        & eligible[EXPANDED_CONTROLS].notna().all(axis=1),
        "H2 mode sensitivity: expanded + mode": common_primary
        & eligible["distrust_index_three"].notna()
        & eligible["viepol"].notna()
        & eligible[EXPANDED_CONTROLS].notna().all(axis=1)
        & eligible["mode"].notna(),
    }
    model_samples = pd.DataFrame(
        [
            {
                "sample": name,
                "retained": int(mask.sum()),
                "dropped_from_outcome_sample": int(len(eligible) - mask.sum()),
                "retained_share": mask.mean(),
                "countries": int(eligible.loc[mask, "cntry"].nunique()),
            }
            for name, mask in model_masks.items()
        ]
    )
    h2_primary = model_masks["H2 primary: H1 + viepol + primary controls"]
    model_country_cells = (
        eligible.loc[h2_primary]
        .groupby("cntry")["voted_populist"]
        .agg(classifiable="size", populist="sum")
        .reset_index()
    )
    model_country_cells["non_populist"] = (
        model_country_cells["classifiable"] - model_country_cells["populist"]
    )

    mode_summary = (
        eligible.assign(
            mode_label=eligible["mode"].map(
                {
                    1: "CAPI face-to-face",
                    2: "web-video interview",
                    3: "CAWI self-completion",
                    4: "paper self-completion",
                }
            )
        )
        .groupby("mode_label", dropna=False, observed=True)["voted_populist"]
        .agg(n="size", populist_share="mean")
        .reset_index()
    )

    model_specification = pd.DataFrame(
        [
            {
                "component": "Country adjustment",
                "primary_rule": "Country fixed intercepts; DE reference",
                "sensitivity_rule": "Re-include CY, GB, LT, and PT once",
            },
            {
                "component": "Weight",
                "primary_rule": "ESS anweight",
                "sensitivity_rule": "Repeat the final specification once unweighted",
            },
            {
                "component": "Age",
                "primary_rule": "(agea - 50) / 10, linear",
                "sensitivity_rule": "No polynomial unless diagnostics show failure",
            },
            {
                "component": "Gender",
                "primary_rule": "Categorical gndr; code 1 (male) reference",
                "sensitivity_rule": "None; report source-variable limitation",
            },
            {
                "component": "Education",
                "primary_rule": "Categorical eisced 1-7; code 4 reference; 55 missing",
                "sensitivity_rule": "None",
            },
            {
                "component": "Political interest",
                "primary_rule": "Excluded from primary control set",
                "sensitivity_rule": "Expanded model: categorical polintr; code 4 reference",
            },
            {
                "component": "Survey mode",
                "primary_rule": "Descriptive only",
                "sensitivity_rule": "One categorical adjustment; code 1 CAPI reference",
            },
            {
                "component": "Missing data",
                "primary_rule": "Model-specific complete cases",
                "sensitivity_rule": "No imputation; report each model sample",
            },
        ]
    )

    weights = pd.DataFrame(
        [
            {
                "weight": "anweight",
                "observed_n": int(eligible["anweight"].notna().sum()),
                "positive_n": int(eligible["anweight"].gt(0).sum()),
                "min": eligible["anweight"].min(),
                "median": eligible["anweight"].median(),
                "mean": eligible["anweight"].mean(),
                "max": eligible["anweight"].max(),
                "kish_effective_n": effective_sample_size(eligible["anweight"]),
            }
        ]
    )
    return {
        "reliability": reliability,
        "reliability_items": reliability_items,
        "pca": pca,
        "item_summary": item_summary,
        "item_distributions": item_distributions,
        "country_reliability": country_reliability,
        "country_reliability_summary": country_reliability_summary,
        "correlations": correlations,
        "domain_correlations": domain_correlations,
        "missingness": missingness,
        "country_variation": country_variation,
        "h2_distributions": h2_distributions,
        "country_distributions": country_distributions,
        "sample_flow": sample_flow,
        "index_comparison": index_comparison,
        "sparse_cells": sparse,
        "model_samples": model_samples,
        "model_country_cells": model_country_cells,
        "mode_summary": mode_summary,
        "model_specification": model_specification,
        "weights": weights,
    }


def make_figures(tables: dict[str, pd.DataFrame]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    missing = tables["missingness"].sort_values("missing_share")
    missing_labels = (
        missing["variable"].map(VARIABLE_LABELS).fillna(missing["variable"])
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(missing_labels, missing["missing_share"] * 100, color="#4c78a8")
    ax.set(
        xlabel="Missing among classifiable voters (%)",
        ylabel="Variable",
        title="Candidate-model variable missingness",
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "stage4_missingness.png", dpi=180)
    plt.close(fig)

    domain = tables["domain_correlations"].set_index("Institution")
    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.imshow(domain, vmin=0, vmax=1, cmap="YlGnBu")
    ax.set_xticks(range(len(domain.columns)), domain.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(domain.index)), domain.index)
    for row in range(len(domain.index)):
        for column in range(len(domain.columns)):
            value = domain.iloc[row, column]
            ax.text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if value > 0.62 else "#1f2933",
                fontsize=8,
            )
    ax.set_title("Exploratory distrust correlations across domains")
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage4_domain_correlation_heatmap.png", dpi=180)
    plt.close(fig)

    viepol = tables["country_variation"].query("variable == 'viepol'").sort_values(
        "weighted_sd"
    )
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.barh(viepol["cntry"], viepol["weighted_sd"], color="#59a14f")
    ax.set(
        xlabel="Weighted within-country standard deviation",
        ylabel="Country",
        title=(
            "Within-country variation in viepol\n"
            "(ordinary people's views should prevail over political elites)"
        ),
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "stage4_viepol_country_sd.png", dpi=180)
    plt.close(fig)

    distributions = tables["country_distributions"]
    measures = distributions["measure"].drop_duplicates().tolist()
    colors = {"0-3": "#4575b4", "4-7": "#ffffbf", "8-10": "#d73027"}
    fig, axes = plt.subplots(1, 2, figsize=(14, 9), sharey=True)
    for ax, measure in zip(axes, measures, strict=True):
        panel = distributions[distributions["measure"].eq(measure)]
        wide = panel.pivot(index="cntry", columns="score_band", values="weighted_share")
        wide = wide[["0-3", "4-7", "8-10"]]
        left = pd.Series(0.0, index=wide.index)
        for band in wide.columns:
            ax.barh(
                wide.index,
                wide[band] * 100,
                left=left * 100,
                color=colors[band],
                label=band,
            )
            left += wide[band]
        ax.set(xlabel="Weighted respondents (%)", title=measure)
        ax.legend(title="Score", loc="lower right")
    axes[0].set_ylabel("Country")
    fig.suptitle("Country distributions of H1 and H2 measures")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage4_h1_h2_country_distributions.png", dpi=180)
    plt.close(fig)

    sparse = tables["sparse_cells"].copy()
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(
        sparse["cntry"], sparse["non_populist"], label="Non-populist", color="#4c78a8"
    )
    ax.barh(
        sparse["cntry"],
        sparse["populist"],
        left=sparse["non_populist"],
        label="Populist",
        color="#f28e2b",
    )
    ax.set(
        xlabel="Classifiable voters",
        ylabel="Country",
        title="Outcome-group sizes by country",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "stage4_country_outcome_cells.png", dpi=180)
    plt.close(fig)


def build_report(tables: dict[str, pd.DataFrame]) -> tuple:
    reliability = tables["reliability"].copy()
    reliability["cronbach_alpha"] = reliability["cronbach_alpha"].map(
        lambda x: f"{x:.3f}"
    )
    item_diagnostics = tables["reliability_items"].copy().round(3)
    pca = tables["pca"].copy().round(3)
    item_summary = tables["item_summary"].copy().round(3)
    correlations = tables["correlations"].copy().round(3)
    country_reliability = tables["country_reliability_summary"].copy().round(3)
    h2_distributions = tables["h2_distributions"].copy().round(3)
    index = tables["index_comparison"].copy()
    index["weighted_mean"] = index["weighted_mean"].map(lambda x: f"{x:.2f}")
    flow = tables["sample_flow"].copy()
    flow["retained_share_of_outcome_sample"] = flow[
        "retained_share_of_outcome_sample"
    ].map(lambda x: f"{x:.1%}")
    sparse = tables["sparse_cells"].query("flag_under_30").copy()
    weight = tables["weights"].copy().round(3)
    variation_flags = (
        tables["country_variation"]
        .query("variable == 'viepol' and (weak_sd_flag or severe_ceiling_flag)")[
            [
                "cntry",
                "n",
                "weighted_mean",
                "weighted_sd",
                "weighted_share_8_10",
                "weighted_share_10",
                "weak_sd_flag",
                "severe_ceiling_flag",
            ]
        ]
        .round(3)
    )
    model_samples = tables["model_samples"].copy()
    model_samples["retained_share"] = model_samples["retained_share"].map(
        lambda x: f"{x:.1%}"
    )
    model_specification = tables["model_specification"].copy()
    mode_summary = tables["mode_summary"].copy().round(3)
    final_sparse = tables["model_country_cells"].copy()
    final_sparse = final_sparse[
        final_sparse[["populist", "non_populist"]].min(axis=1).lt(MIN_OUTCOME_CELL)
    ]
    decisions = pd.DataFrame(
        [
            {
                "Decision": "Distrust completeness",
                "Outcome": "All three items required",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "Primary H2 indicator",
                "Outcome": "viepol alone",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "wpestop role",
                "Outcome": "Separate Stage 7 sensitivity indicator",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "Missing data",
                "Outcome": "Model-specific complete cases; no imputation",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "Country treatment",
                "Outcome": "Fixed intercepts; >=30 per outcome group",
                "Reviewer status": "Accepted by owner; Latvia retained",
            },
            {
                "Decision": "Primary weight",
                "Outcome": "anweight; one unweighted comparison",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "Controls",
                "Outcome": "Primary agea + gndr + eisced; expanded adds polintr",
                "Reviewer status": "Accepted by owner",
            },
            {
                "Decision": "Survey mode",
                "Outcome": "Descriptive; one categorical-adjustment sensitivity",
                "Reviewer status": "Accepted by owner",
            },
        ]
    )
    md = f"""# Stage 4 measurement and sample diagnostics

This report reproduces decision evidence from canonical Table C. All registered
Stage 4 items and interpretations were accepted by the project owner on 2026-09-08.

## Political-distrust measurement

{markdown_table(reliability)}

{markdown_table(item_diagnostics)}

{markdown_table(item_summary)}

The three source items are reverse-coded from their original 0-10 trust scales, so
higher values indicate greater distrust. Cronbach's alpha summarizes the internal
consistency of the proposed three-item composite; it is not evidence of inter-rater
agreement or, by itself, proof that the scale is unidimensional. Corrected item-total
correlations use complete rows and correlate each item with the sum of the other two.
The exact score distributions are in
`outputs/tables/stage4_item_distributions.csv`.

### Pairwise correlations with H2 indicators

{markdown_table(correlations)}

## One-dimensionality check

{markdown_table(pca)}

The PCA uses the complete-case item correlation matrix. A dominant first component,
positive first-component loadings, and remaining eigenvalues below one support a
concise one-dimensional summary. This is a diagnostic, not a substitute for the
construct argument.

## Proportionate country-level reliability check

{markdown_table(country_reliability)}

The full country table is `outputs/tables/stage4_country_reliability.csv`. It is
reported as a compact heterogeneity check rather than as 27 separate scale-selection
tests.

{markdown_table(index)}

## Appendix: trust-domain specificity

All trust items are reverse-coded only to give them a common direction: higher values
mean greater distrust. The legal system, police, supranational institutions,
scientists, and other people are exploratory comparison domains; they are not added
to the primary political-distrust index. The appendix asks whether parliament,
politicians, and political parties correlate more strongly with one another than with
the comparison domains.

![Distrust correlations across domains](../figures/stage4_domain_correlation_heatmap.png)

The exact matrix is available in `outputs/tables/stage4_domain_correlations.csv`.

![Missingness](../figures/stage4_missingness.png)

## Candidate model-sample flow

{markdown_table(flow)}

## Fully specified candidate model samples

{markdown_table(model_samples)}

The primary H1 and H2 samples use model-specific complete cases. The loss remains
small enough that no imputation or attrition model is added. H2 requires the H1 index
because it tests whether `viepol` contributes beyond political distrust.

The accepted 30-per-outcome stability screen is applied to the classifiable outcome
sample before covariate missingness. After complete-case filtering, the following H2
country falls just below 30 and is retained under that pre-specified ordering:

{markdown_table(final_sparse) if len(final_sparse) else 'None.'}

The project owner accepted retaining Latvia under this pre-specified ordering rather
than silently changing the country list after covariate filtering.

## H2 within-country variation

{markdown_table(h2_distributions)}

The pooled weighted results reproduce the exploratory pattern: `viepol` retains
variation but is concentrated at 8-10, while `wpestop` has the stronger ceiling.

Flags use pre-specified descriptive thresholds: weighted SD below {WEAK_VIEPOL_SD:.2f},
weighted share at 8-10 of at least {SEVERE_VIEPOL_SHARE_8_10:.0%}, or share at 10
of at least {SEVERE_VIEPOL_SHARE_10:.0%}. They prompt interpretation and do not exclude
a country.

{markdown_table(variation_flags)}

![Within-country viepol variation](../figures/stage4_viepol_country_sd.png)

## Country distributions of the H1 and H2 measures

The figure reports weighted shares in three descriptive score bands. For the H1 index,
8-10 means high political distrust. For `viepol`, 8-10 means strong support for
ordinary people's views prevailing over political elites. These bands make the
distributions readable; they are not cutoffs used in the regression models. The
underlying models retain the original scores.

![Country distributions of H1 and H2 measures](../figures/stage4_h1_h2_country_distributions.png)

Exact weighted shares are available in
`outputs/tables/stage4_country_distributions.csv`. Standard deviations remain in the
technical country-variation table because they answer whether enough within-country
variation exists for modelling.

## Country outcome cells

{markdown_table(sparse)}

![Outcome cells](../figures/stage4_country_outcome_cells.png)

## Weight diagnostics

{markdown_table(weight)}

ESS recommends `anweight` for all analyses. It combines post-stratification and
population-size weighting and is therefore the primary weight. The sole weight
sensitivity repeats the final model without weights; no menu of alternative weights
is planned. Source: [ESS weighting guidance](https://www.europeansocialsurvey.org/methodology/ess-methodology/data-processing-and-archiving/weighting).

## Model specification handed to Stage 5-6

{markdown_table(model_specification)}

Country adjustment is one logistic-regression specification with country fixed
intercepts, not an estimator tournament. Survey mode is descriptive in the main
analysis because collection-mode families are strongly tied to country in Round 10;
one categorical-adjustment sensitivity checks residual within-country mode imbalance.
No H3 or interaction is introduced.

### Survey-mode description

{markdown_table(mode_summary)}

These are unadjusted composition statistics and must not be interpreted as mode
effects because country and collection-mode family are strongly confounded.

## Decision register

{markdown_table(decisions)}

The script never changes owner-review fields. The corresponding confirmations are
recorded separately in `plans/review-ledger.csv` and the accepted analytical choices
are retained in `docs/methods_decision_log.md`.
"""
    md_path = REPORTS / "measurement_diagnostics.md"
    md_path.write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Stage 4 diagnostics</title><style>body{{font:16px/1.5 system-ui;max-width:1050px;margin:auto;padding:2rem;color:#24303b}}h1,h2{{color:#16324f}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}th,td{{border:1px solid #dbe4ea;padding:.45rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5;padding:.1rem .25rem}}</style></head><body>{rendered}</body></html>"""
    html_path = REPORTS / "measurement_diagnostics.html"
    html_path.write_text(html, encoding="utf-8")
    return md_path, html_path


def main() -> None:
    for directory in (REPORTS, FIGURES, TABLES):
        directory.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(ANALYSIS_BASE, low_memory=False)
    validate_input(data)
    tables = build_tables(data)
    for name, table in tables.items():
        table.to_csv(TABLES / f"stage4_{name}.csv", index=False)
    make_figures(tables)
    md_path, html_path = build_report(tables)
    print(f"Wrote {md_path.relative_to(ROOT)}")
    print(f"Wrote {html_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
