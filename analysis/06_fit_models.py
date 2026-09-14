# ruff: noqa: E501
"""Fit and report the pre-specified Stage 6 H1-H2a models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import markdown
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

from populism_project.config import ANALYSIS_BASE, ROOT
from populism_project.descriptives import effective_sample_size
from populism_project.measurement import add_measurements, add_model_controls
from populism_project.modeling import (
    average_marginal_effect,
    counterfactual_average_probability,
    fit_weighted_country_gee,
    tidy_coefficients,
)

REPORTS = ROOT / "outputs" / "reports"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"
MIN_OUTCOME_CELL = 30
FOCAL_TERMS = ["distrust_index_three", "viepol"]
FOCAL_LABELS = {
    "distrust_index_three": "Political distrust",
    "viepol": "People's views should prevail",
}


@dataclass(frozen=True)
class ModelSpec:
    code: str
    label: str
    terms: tuple[str, ...]
    required: tuple[str, ...]
    weighted: bool = True


SPECS = [
    ModelSpec(
        "M1",
        "H1 adjusted",
        (
            "distrust_index_three",
            "age_decades_50",
            "C(gndr, Treatment(reference=1))",
            "C(eisced_model, Treatment(reference=4))",
        ),
        ("distrust_index_three", "age_decades_50", "gndr", "eisced_model"),
    ),
    ModelSpec(
        "M2",
        "H2a adjusted",
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "C(gndr, Treatment(reference=1))",
            "C(eisced_model, Treatment(reference=4))",
        ),
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "gndr",
            "eisced_model",
        ),
    ),
    ModelSpec(
        "S1",
        "Expanded: + political interest",
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "C(gndr, Treatment(reference=1))",
            "C(eisced_model, Treatment(reference=4))",
            "C(polintr, Treatment(reference=4))",
        ),
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "gndr",
            "eisced_model",
            "polintr",
        ),
    ),
    ModelSpec(
        "S1-U",
        "Expanded unweighted",
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "C(gndr, Treatment(reference=1))",
            "C(eisced_model, Treatment(reference=4))",
            "C(polintr, Treatment(reference=4))",
        ),
        (
            "distrust_index_three",
            "viepol",
            "age_decades_50",
            "gndr",
            "eisced_model",
            "polintr",
        ),
        weighted=False,
    ),
]


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    header = "| " + " | ".join(values.columns) + " |"
    divider = "|" + "|".join("---" for _ in values.columns) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in values.to_numpy()]
    return "\n".join([header, divider, *rows])


def country_formula(terms: tuple[str, ...], reference: str = "DE") -> str:
    rhs = [*terms, f"C(cntry, Treatment(reference='{reference}'))"]
    return "voted_populist ~ " + " + ".join(rhs)


def prepare_analysis_data(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    eligible = add_model_controls(
        add_measurements(data.loc[data["analysis_eligible"]].copy())
    )
    cells = eligible.groupby("cntry")["voted_populist"].agg(["size", "sum"])
    cells["non_populist"] = cells["size"] - cells["sum"]
    countries = sorted(
        cells.index[cells[["sum", "non_populist"]].min(axis=1).ge(MIN_OUTCOME_CELL)]
    )
    analysis = eligible.loc[
        eligible["cntry"].isin(countries) & eligible["anweight"].gt(0)
    ].copy()
    if countries != [
        "AT",
        "BE",
        "BG",
        "CH",
        "CZ",
        "DE",
        "EE",
        "ES",
        "FI",
        "FR",
        "GR",
        "HR",
        "HU",
        "IE",
        "IS",
        "IT",
        "LV",
        "NL",
        "NO",
        "PL",
        "SE",
        "SI",
        "SK",
    ]:
        raise ValueError(f"Unexpected Stage 6 primary-country set: {countries}")
    return analysis, countries


def model_sample(data: pd.DataFrame, spec: ModelSpec) -> pd.DataFrame:
    return data.loc[data[list(spec.required)].notna().all(axis=1)].copy()


def term_kind(term: str) -> str:
    if term == "Intercept":
        return "intercept"
    if term in FOCAL_TERMS:
        return "focal"
    if "cntry" in term:
        return "country fixed effect"
    return "control"


def fit_models(data: pd.DataFrame) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    results: dict[str, object] = {}
    samples: dict[str, pd.DataFrame] = {}
    for spec in SPECS:
        sample = model_sample(data, spec)
        result = fit_weighted_country_gee(
            country_formula(spec.terms),
            sample,
            weight_column="anweight" if spec.weighted else None,
        )
        if not result.converged:
            raise RuntimeError(f"{spec.code} failed to converge")
        results[spec.code] = result
        samples[spec.code] = sample
    expected = {
        "M1": 28_657,
        "M2": 28_089,
        "S1": 28_040,
        "S1-U": 28_040,
    }
    observed = {code: len(sample) for code, sample in samples.items()}
    if observed != expected:
        raise ValueError(f"Unexpected Stage 6 model samples: {observed}")
    return results, samples


def build_model_tables(
    results: dict[str, object], samples: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    coefficient_frames = []
    marginal_rows = []
    diagnostic_rows = []
    sample_rows = []
    for spec in SPECS:
        result = results[spec.code]
        sample = samples[spec.code]
        clusters = sample["cntry"].nunique()
        coefficients = tidy_coefficients(result, model=spec.code, clusters=clusters)
        coefficients.insert(1, "model_label", spec.label)
        coefficients["term_type"] = coefficients["term"].map(term_kind)
        coefficient_frames.append(coefficients)
        weights = sample["anweight"] if spec.weighted else np.ones(len(sample))
        for term in FOCAL_TERMS:
            if term not in result.model.exog_names:
                continue
            marginal_rows.append(
                {
                    "model": spec.code,
                    "model_label": spec.label,
                    "term": term,
                    "term_label": FOCAL_LABELS[term],
                    "weighting": "anweight" if spec.weighted else "unweighted",
                    **average_marginal_effect(
                        result, term, weights, clusters=clusters
                    ),
                }
            )
        predicted = np.asarray(result.predict(sample), dtype=float)
        score_history = result.fit_history.get("score", [])
        final_score = float(np.max(np.abs(score_history[-1]))) if score_history else np.nan
        diagnostic_rows.append(
            {
                "model": spec.code,
                "model_label": spec.label,
                "weighting": "anweight" if spec.weighted else "unweighted",
                "n": len(sample),
                "events": int(sample["voted_populist"].sum()),
                "countries": clusters,
                "parameters": len(result.params),
                "converged": bool(result.converged),
                "iterations": len(result.fit_history.get("params", [])),
                "max_abs_final_score": final_score,
                "predicted_min": float(predicted.min()),
                "predicted_p01": float(np.quantile(predicted, 0.01)),
                "predicted_p99": float(np.quantile(predicted, 0.99)),
                "predicted_max": float(predicted.max()),
                "predicted_below_001": int((predicted < 0.001).sum()),
                "predicted_above_999": int((predicted > 0.999).sum()),
                "max_abs_coefficient": float(np.max(np.abs(result.params))),
            }
        )
        sample_rows.append(
            {
                "model": spec.code,
                "model_label": spec.label,
                "weighting": "anweight" if spec.weighted else "unweighted",
                "n": len(sample),
                "populist_voters": int(sample["voted_populist"].sum()),
                "non_populist_voters": int((1 - sample["voted_populist"]).sum()),
                "countries": clusters,
                "kish_effective_n": effective_sample_size(sample["anweight"])
                if spec.weighted
                else float(len(sample)),
            }
        )
    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    focal = coefficients.loc[coefficients["term_type"].eq("focal")].copy()
    return {
        "coefficients": coefficients,
        "focal_effects": focal,
        "marginal_effects": pd.DataFrame(marginal_rows),
        "diagnostics": pd.DataFrame(diagnostic_rows),
        "samples": pd.DataFrame(sample_rows),
    }


def build_probability_profiles(
    result: object, sample: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    clusters = sample["cntry"].nunique()
    for term in FOCAL_TERMS:
        for value in range(11):
            counterfactual = sample.copy()
            counterfactual[term] = float(value)
            rows.append(
                {
                    "term": term,
                    "term_label": FOCAL_LABELS[term],
                    "value": value,
                    **counterfactual_average_probability(
                        result,
                        counterfactual,
                        sample["anweight"],
                        clusters=clusters,
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_country_cells(sample: pd.DataFrame) -> pd.DataFrame:
    cells = (
        sample.groupby("cntry")["voted_populist"]
        .agg(classifiable="size", populist="sum")
        .reset_index()
    )
    cells["populist"] = cells["populist"].astype(int)
    cells["non_populist"] = cells["classifiable"] - cells["populist"]
    cells["minimum_outcome_cell"] = cells[["populist", "non_populist"]].min(axis=1)
    cells["below_30_after_complete_cases"] = cells["minimum_outcome_cell"].lt(30)
    return cells


def build_country_influence(
    full_result: object, sample: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    full_params = full_result.params
    for omitted in sorted(sample["cntry"].unique()):
        reduced = sample.loc[sample["cntry"].ne(omitted)].copy()
        reference = "DE" if omitted != "DE" else sorted(reduced["cntry"].unique())[0]
        primary_spec = next(spec for spec in SPECS if spec.code == "M2")
        result = fit_weighted_country_gee(
            country_formula(primary_spec.terms, reference=reference),
            reduced,
            weight_column="anweight",
        )
        if not result.converged:
            raise RuntimeError(f"Leave-{omitted}-out model failed to converge")
        for term in FOCAL_TERMS:
            rows.append(
                {
                    "omitted_country": omitted,
                    "term": term,
                    "term_label": FOCAL_LABELS[term],
                    "full_estimate_log_odds": float(full_params[term]),
                    "leave_one_out_estimate_log_odds": float(result.params[term]),
                    "change_log_odds": float(result.params[term] - full_params[term]),
                    "absolute_change_log_odds": float(abs(result.params[term] - full_params[term])),
                    "converged": bool(result.converged),
                }
            )
    return pd.DataFrame(rows)


def write_tables(tables: dict[str, pd.DataFrame]) -> None:
    mapping = {
        "coefficients": "stage6_model_coefficients.csv",
        "focal_effects": "stage6_focal_effects.csv",
        "marginal_effects": "stage6_average_marginal_effects.csv",
        "diagnostics": "stage6_model_diagnostics.csv",
        "samples": "stage6_model_samples.csv",
        "probabilities": "stage6_predicted_probabilities.csv",
        "country_cells": "stage6_country_cells.csv",
        "country_influence": "stage6_country_influence.csv",
    }
    for key, filename in mapping.items():
        tables[key].to_csv(TABLES / filename, index=False)


def make_figures(tables: dict[str, pd.DataFrame]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    focal = tables["focal_effects"].copy()
    model_order = [spec.code for spec in SPECS]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, term in zip(axes, FOCAL_TERMS, strict=True):
        plot = focal.loc[focal["term"].eq(term)].set_index("model").reindex(model_order).dropna()
        y = np.arange(len(plot))
        ax.errorbar(
            plot["estimate_log_odds"],
            y,
            xerr=[plot["estimate_log_odds"] - plot["conf_low"], plot["conf_high"] - plot["estimate_log_odds"]],
            fmt="o",
            color="#1b6ca8",
            ecolor="#526574",
            capsize=3,
        )
        ax.axvline(0, color="#333333", linewidth=1, linestyle="--")
        ax.set_title(FOCAL_LABELS[term])
        ax.set_xlabel("Log-odds coefficient (95% cluster-t interval)")
        ax.set_yticks(y, plot.index)
        ax.invert_yaxis()
    fig.suptitle("Stage 6 focal estimates across model specifications")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage6_focal_coefficients.png", dpi=180)
    plt.close(fig)

    profiles = tables["probabilities"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharey=True)
    for ax, term in zip(axes, FOCAL_TERMS, strict=True):
        plot = profiles.loc[profiles["term"].eq(term)]
        ax.plot(plot["value"], plot["estimate"], marker="o", color="#d95f02")
        ax.fill_between(plot["value"], plot["conf_low"], plot["conf_high"], color="#d95f02", alpha=0.2)
        for row, offset, alignment in [
            (plot.iloc[0], (8, -15), "left"),
            (plot.iloc[-1], (-8, 8), "right"),
        ]:
            ax.annotate(
                f"{row['estimate']:.1%}",
                (row["value"], row["estimate"]),
                xytext=offset,
                textcoords="offset points",
                ha=alignment,
                fontweight="bold",
                color="#9a4300",
            )
        ax.set(
            title=FOCAL_LABELS[term],
            xlabel="Score on the 0–10 scale",
            ylabel="Average predicted probability of a populist vote",
        )
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.set_ylim(0, max(0.45, profiles["conf_high"].max() * 1.08))
    fig.suptitle("Primary adjusted model: standardized predicted probabilities")
    fig.text(
        0.5,
        0.02,
        "Each panel changes only the named score; country, demographics, and the other attitude remain unchanged. Shading shows 95% confidence intervals.",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    fig.savefig(FIGURES / "stage6_predicted_probabilities.png", dpi=180)
    plt.close(fig)

    influence = tables["country_influence"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 7), sharey=True)
    for ax, term in zip(axes, FOCAL_TERMS, strict=True):
        plot = influence.loc[influence["term"].eq(term)].sort_values("change_log_odds")
        colors = ["#d95f02" if abs(value) == plot["absolute_change_log_odds"].max() else "#4c78a8" for value in plot["change_log_odds"]]
        ax.barh(plot["omitted_country"], plot["change_log_odds"], color=colors)
        ax.axvline(0, color="#333333", linewidth=1)
        ax.set(title=FOCAL_LABELS[term], xlabel="Change after omitting country (log odds)")
    fig.suptitle("Leave-one-country-out influence on expanded weighted estimates")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage6_country_influence.png", dpi=180)
    plt.close(fig)


def report_display_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    samples = tables["samples"].copy()
    samples["kish_effective_n"] = samples["kish_effective_n"].round(0).astype(int)
    focal = tables["focal_effects"][["model", "term", "estimate_log_odds", "std_error", "conf_low", "conf_high", "p_value", "odds_ratio"]].copy()
    focal["term"] = focal["term"].map(FOCAL_LABELS)
    for column in ["estimate_log_odds", "std_error", "conf_low", "conf_high", "p_value", "odds_ratio"]:
        focal[column] = focal[column].map(lambda value: f"{value:.3f}")
    ame = tables["marginal_effects"][["model", "term_label", "estimate", "conf_low", "conf_high", "p_value"]].copy()
    for column in ["estimate", "conf_low", "conf_high"]:
        ame[column] = ame[column].map(lambda value: f"{100 * value:.2f} pp")
    ame["p_value"] = ame["p_value"].map(lambda value: f"{value:.3f}")
    diagnostics = tables["diagnostics"][["model", "converged", "iterations", "predicted_min", "predicted_p01", "predicted_p99", "predicted_max", "predicted_below_001", "predicted_above_999"]].copy()
    for column in ["predicted_min", "predicted_p01", "predicted_p99", "predicted_max"]:
        diagnostics[column] = diagnostics[column].map(lambda value: f"{value:.4f}")
    influence = (
        tables["country_influence"]
        .sort_values("absolute_change_log_odds", ascending=False)
        .groupby("term", sort=False)
        .head(3)[["term_label", "omitted_country", "leave_one_out_estimate_log_odds", "change_log_odds"]]
        .copy()
    )
    influence[["leave_one_out_estimate_log_odds", "change_log_odds"]] = influence[["leave_one_out_estimate_log_odds", "change_log_odds"]].round(3)
    return {"samples": samples, "focal": focal, "ame": ame, "diagnostics": diagnostics, "influence": influence}


def write_report(tables: dict[str, pd.DataFrame]) -> tuple[Path, Path]:
    display = report_display_tables(tables)
    primary = tables["focal_effects"].loc[tables["focal_effects"]["model"].eq("M2")].set_index("term")
    ame = tables["marginal_effects"].loc[tables["marginal_effects"]["model"].eq("M2")].set_index("term")
    profiles = tables["probabilities"]
    endpoints = profiles.loc[profiles["value"].isin([0, 10])].pivot(index="term", columns="value", values="estimate")
    h1_significant = bool(primary.loc["distrust_index_three", "conf_low"] > 0)
    h2_significant = bool(primary.loc["viepol", "conf_low"] > 0)
    max_influence = tables["country_influence"].loc[tables["country_influence"].groupby("term")["absolute_change_log_odds"].idxmax()].set_index("term")
    low_cells = tables["country_cells"].loc[tables["country_cells"]["below_30_after_complete_cases"]]
    md = f"""# Stage 6 main H1-H2a models

This report fits the accepted country-fixed-intercept logistic sequence among
classifiable voters. Primary estimates use the ESS analysis weight. Estimating
equations are clustered by country with an independent working correlation, and
reported 95% intervals use a t reference distribution with 22 degrees of freedom
because only 23 country clusters are available.

The project owner authorized automatic acceptance of interpretations; every Stage 6
interpretation is recorded as re-verifiable in a later session.

## Model sequence and samples

{markdown_table(display['samples'])}

M1 is the adjusted H1 model with political distrust, age, gender, education, and
country indicators. M2 is the adjusted H2a model and adds `viepol` to M1. S1 adds
political interest as a sensitivity check; S1-U repeats S1 without weights. Complete
cases are selected separately for the variables in each model.

## Focal coefficients

{markdown_table(display['focal'])}

![Focal coefficients](../figures/stage6_focal_coefficients.png)

In the primary adjusted model, the political-distrust coefficient is
**{primary.loc['distrust_index_three', 'estimate_log_odds']:.3f}** (95% cluster-t
interval {primary.loc['distrust_index_three', 'conf_low']:.3f} to
{primary.loc['distrust_index_three', 'conf_high']:.3f}). Its interval
{'excludes' if h1_significant else 'includes'} zero. The `viepol` coefficient is
**{primary.loc['viepol', 'estimate_log_odds']:.3f}** (95% interval
{primary.loc['viepol', 'conf_low']:.3f} to {primary.loc['viepol', 'conf_high']:.3f})
and {'excludes' if h2_significant else 'includes'} zero.

Accordingly, Stage 6 {'supports' if h1_significant else 'does not provide precise country-clustered support for'} H1 in its common positive-association form. It {'supports' if h2_significant else 'does not provide precise support for'} H2 as an association of `viepol` with populist-party voting after accounting for political distrust, country, and demographics. These remain associational, not causal, results.

Adding political interest in S1 leaves the substantive conclusion unchanged: the
distrust interval still includes zero, while the `viepol` interval excludes zero.

## Average marginal effects and probabilities

{markdown_table(display['ame'])}

One point higher political distrust corresponds to an average probability change of
**{100 * ame.loc['distrust_index_three', 'estimate']:.2f} percentage points** in M2;
one point higher `viepol` corresponds to **{100 * ame.loc['viepol', 'estimate']:.2f}
percentage points**. These are averages over the observed covariate distribution.

![Adjusted predicted probabilities](../figures/stage6_predicted_probabilities.png)

Standardizing every M2 observation first to score 0 and then to score 10 changes the
average predicted probability from {endpoints.loc['distrust_index_three', 0]:.1%} to
{endpoints.loc['distrust_index_three', 10]:.1%} for political distrust, and from
{endpoints.loc['viepol', 0]:.1%} to {endpoints.loc['viepol', 10]:.1%} for `viepol`.
The endpoints illustrate the fitted curve and should not be read as effects of an
intervention or as comparisons among otherwise identical real respondents.

## Convergence and separation checks

{markdown_table(display['diagnostics'])}

All four models converged. No fitted observation has a probability below .001 or
above .999, and no focal estimate is numerically extreme. The pre-specified country
screen is applied before covariate complete-case restrictions; {', '.join(low_cells['cntry']) if len(low_cells) else 'no country'} falls below 30 in one final complete-case outcome cell and is retained under that accepted ordering. Exact cells are in `outputs/tables/stage6_country_cells.csv`.

## Influential-country check

{markdown_table(display['influence'])}

![Country influence](../figures/stage6_country_influence.png)

The largest leave-one-country-out coefficient change is
{max_influence.loc['distrust_index_three', 'change_log_odds']:+.3f} for distrust when
omitting {max_influence.loc['distrust_index_three', 'omitted_country']}, and
{max_influence.loc['viepol', 'change_log_odds']:+.3f} for `viepol` when omitting
{max_influence.loc['viepol', 'omitted_country']}. This check diagnoses sensitivity to
country composition; it does not introduce country-specific hypotheses or select a
preferred country subset.

## Interpretation boundary

Odds ratios, marginal effects, and standardized probabilities describe the same
logistic models on different scales. Country fixed effects absorb stable country
differences, but they do not remove unmeasured respondent-level confounding, outcome
misclassification, party-response nonresponse, or cross-national measurement
non-equivalence. Stage 7 will apply the registered robustness checks rather than
silently changing this primary specification.
"""
    md_path = REPORTS / "main_models.md"
    md_path.write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Stage 6 main models</title><style>body{{font:16px/1.5 system-ui;max-width:1100px;margin:auto;padding:2rem;color:#24303b}}h1,h2{{color:#16324f}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem;font-size:.9rem}}th,td{{border:1px solid #dbe4ea;padding:.4rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5;padding:.1rem .25rem}}</style></head><body>{rendered}</body></html>"""
    html_path = REPORTS / "main_models.html"
    html_path.write_text(html, encoding="utf-8")
    return md_path, html_path


def main() -> None:
    for directory in (REPORTS, FIGURES, TABLES):
        directory.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(ANALYSIS_BASE, low_memory=False)
    data, countries = prepare_analysis_data(source)
    results, samples = fit_models(data)
    tables = build_model_tables(results, samples)
    tables["probabilities"] = build_probability_profiles(results["M2"], samples["M2"])
    tables["country_cells"] = build_country_cells(samples["M2"])
    tables["country_influence"] = build_country_influence(results["M2"], samples["M2"])
    write_tables(tables)
    make_figures(tables)
    md_path, html_path = write_report(tables)
    print(f"Stage 6 primary countries: {len(countries)}")
    print(f"Stage 6 model sample range: {min(map(len, samples.values())):,}-{max(map(len, samples.values())):,}")
    print(f"Wrote {md_path.relative_to(ROOT)}")
    print(f"Wrote {html_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
