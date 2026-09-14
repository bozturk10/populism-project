# ruff: noqa: E501
"""Estimate and synthesize exploratory country-specific H1-H2 associations."""

from __future__ import annotations

import markdown
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from populism_project.config import ANALYSIS_BASE, ROOT
from populism_project.heterogeneity import (
    benjamini_hochberg,
    empirical_bayes_shrink,
    random_effects_meta,
)
from populism_project.measurement import (
    add_measurements,
    add_model_controls,
    effective_sample_size,
)
from populism_project.modeling import (
    average_marginal_effect,
    fit_weighted_country_gee,
    tidy_coefficients,
)

REPORTS = ROOT / "outputs" / "reports"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
TERMS = ["distrust_index_three", "viepol"]
LABELS = {"distrust_index_three": "Representative-political-institution distrust", "viepol": "People's views should prevail"}
COLORS = {"positive_interval_above_zero": "#2166ac", "positive_interval_includes_zero": "#92c5de", "negative_interval_includes_zero": "#f4a582", "negative_interval_below_zero": "#b2182b", "not_estimable": "#777777"}


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(values.columns) + " |", "|" + "|".join("---" for _ in values.columns) + "|", *["| " + " | ".join(row) + " |" for row in values.to_numpy()]])


def prepare(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    eligible = add_model_controls(add_measurements(data.loc[data["analysis_eligible"]].copy()))
    cells = eligible.groupby("cntry")["voted_populist"].agg(["size", "sum"])
    cells["non"] = cells["size"] - cells["sum"]
    countries = sorted(cells.index[cells[["sum", "non"]].min(axis=1).ge(30)])
    sample = eligible.loc[eligible["cntry"].isin(countries) & eligible["anweight"].gt(0) & eligible[[*TERMS, "age_decades_50", "gndr", "eisced_model", "psu", "stratum"]].notna().all(axis=1)].copy()
    if len(sample) != 28_089 or len(countries) != 23:
        raise ValueError("Stage 9 must reproduce the 28,089-person, 23-country M2 sample")
    return sample, countries


def design_audit(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country, group in sample.groupby("cntry", sort=True):
        psu_sizes = group.groupby("psu").size()
        psus_per_stratum = group.groupby("stratum")["psu"].nunique()
        rows.append({"cntry": country, "n": len(group), "psu_count": group["psu"].nunique(), "stratum_count": group["stratum"].nunique(), "singleton_psu_share": float((psu_sizes == 1).mean()), "single_psu_stratum_share": float((psus_per_stratum == 1).mean()), "psu_missing": int(group["psu"].isna().sum()), "stratum_missing": int(group["stratum"].isna().sum()), "variance_method": "anweight-weighted logistic GEE; PSU-cluster robust; strata audited but not Taylor-adjusted"})
    return pd.DataFrame(rows)


def evidence_category(estimate: float, low: float, high: float) -> str:
    if not np.isfinite([estimate, low, high]).all():
        return "not_estimable"
    if low > 0:
        return "positive_interval_above_zero"
    if high < 0:
        return "negative_interval_below_zero"
    return "positive_interval_includes_zero" if estimate >= 0 else "negative_interval_includes_zero"


def fit_countries(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    effects, diagnostics = [], []
    formula = "voted_populist ~ distrust_index_three + viepol + age_decades_50 + C(gndr, Treatment(reference=1)) + C(eisced_model, Treatment(reference=4))"
    for country, group in sample.groupby("cntry", sort=True):
        result = fit_weighted_country_gee(formula, group, weight_column="anweight", group_column="psu")
        psus = group["psu"].nunique()
        coefficients = tidy_coefficients(result, model=country, clusters=psus, terms=TERMS)
        weights = group["anweight"]
        for row in coefficients.to_dict("records"):
            term = row["term"]
            marginal = average_marginal_effect(result, term, weights, clusters=psus)
            effects.append({"cntry": country, "term": term, "term_label": LABELS[term], "n": len(group), "populist": int(group["voted_populist"].sum()), "non_populist": int((1 - group["voted_populist"]).sum()), "psu_count": psus, "kish_effective_n": effective_sample_size(weights), **{key: value for key, value in row.items() if key != "model"}, "ame": marginal["estimate"], "ame_std_error": marginal["std_error"], "ame_low": marginal["conf_low"], "ame_high": marginal["conf_high"], "evidence_category": evidence_category(row["estimate_log_odds"], row["conf_low"], row["conf_high"])})
        predicted = np.asarray(result.predict(group))
        diagnostics.append({"cntry": country, "n": len(group), "populist": int(group["voted_populist"].sum()), "non_populist": int((1-group["voted_populist"]).sum()), "psu_count": psus, "parameters": len(result.params), "converged": bool(result.converged), "predicted_min": predicted.min(), "predicted_max": predicted.max(), "below_001": int((predicted < .001).sum()), "above_999": int((predicted > .999).sum()), "max_abs_coefficient": float(np.abs(result.params).max())})
    frame = pd.DataFrame(effects)
    frame["fdr_q_value"] = frame.groupby("term")["p_value"].transform(lambda values: benjamini_hochberg(values.to_numpy()))
    return frame, pd.DataFrame(diagnostics)


def synthesize(effects: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, shrunken = [], []
    for term, group in effects.groupby("term", sort=False):
        meta = random_effects_meta(group["estimate_log_odds"].to_numpy(), group["std_error"].pow(2).to_numpy())
        rows.append({"term": term, "term_label": LABELS[term], **meta})
        shrunk = empirical_bayes_shrink(group["estimate_log_odds"].to_numpy(), group["std_error"].pow(2).to_numpy(), meta["estimate"], meta["tau2"])
        for country, observed, value in zip(group["cntry"], group["estimate_log_odds"], shrunk, strict=True):
            shrunken.append({"cntry": country, "term": term, "observed_estimate": observed, "shrunken_estimate": value, "meta_mean": meta["estimate"], "tau2": meta["tau2"]})
    return pd.DataFrame(rows), pd.DataFrame(shrunken)


def direction_summary(effects: pd.DataFrame) -> pd.DataFrame:
    result = effects.groupby(["term", "term_label", "evidence_category"]).size().rename("countries").reset_index()
    result["share"] = result["countries"] / result.groupby("term")["countries"].transform("sum")
    positive = effects.assign(positive=lambda x: x["estimate_log_odds"] > 0).groupby(["term", "term_label"])["positive"].agg(positive_countries="sum", total_countries="size").reset_index()
    positive["positive_share"] = positive["positive_countries"] / positive["total_countries"]
    return result.merge(positive, on=["term", "term_label"])


def forest_plot(effects: pd.DataFrame, term: str, filename: str) -> None:
    plot = effects.loc[effects["term"].eq(term)].sort_values("ame")
    y = np.arange(len(plot))
    fig, ax = plt.subplots(figsize=(9, 9))
    for index, (_, row) in enumerate(plot.iterrows()):
        ax.errorbar(row["ame"] * 100, index, xerr=[[100*(row["ame"]-row["ame_low"])], [100*(row["ame_high"]-row["ame"])]], fmt="o", color=COLORS[row["evidence_category"]], ecolor=COLORS[row["evidence_category"]], capsize=3)
    ax.axvline(0, color="#333", linestyle="--", linewidth=1)
    ax.set_yticks(y, plot["cntry"])
    ax.set_xlabel("Average marginal effect per one-point increase (percentage points)")
    ax.set_title(f"Country-specific {LABELS[term]} associations")
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=180)
    plt.close(fig)


def shrinkage_plot(shrunken: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 8))
    for ax, term in zip(axes, TERMS, strict=True):
        plot = shrunken.loc[shrunken["term"].eq(term)].sort_values("observed_estimate")
        y = np.arange(len(plot))
        ax.scatter(plot["observed_estimate"], y, label="Unpooled", color="#d95f02")
        ax.scatter(plot["shrunken_estimate"], y, label="Empirical Bayes", color="#1b6ca8")
        for index, row in enumerate(plot.itertuples()):
            ax.plot([row.observed_estimate, row.shrunken_estimate], [index, index], color="#aaa", linewidth=.8)
        ax.axvline(plot["meta_mean"].iloc[0], color="#333", linestyle="--")
        ax.set_yticks(y, plot["cntry"])
        ax.set_title(LABELS[term])
        ax.set_xlabel("Log-odds coefficient")
    axes[1].legend(loc="lower right")
    fig.suptitle("Unpooled and random-effects-shrunken country estimates")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage9_country_shrinkage.png", dpi=180)
    plt.close(fig)


def write_report(effects: pd.DataFrame, diagnostics: pd.DataFrame, directions: pd.DataFrame, meta: pd.DataFrame, audit: pd.DataFrame) -> None:
    summary = directions[["term_label", "evidence_category", "countries", "share", "positive_countries", "total_countries", "positive_share"]].copy()
    summary[["share", "positive_share"]] = summary[["share", "positive_share"]].map(lambda x: f"{x:.1%}")
    meta_display = meta[["term_label", "k", "estimate", "conf_low", "conf_high", "tau2", "i2", "prediction_low", "prediction_high"]].copy().round(3)
    diag_flags = diagnostics.loc[(diagnostics["below_001"] > 0) | (diagnostics["above_999"] > 0) | ~diagnostics["converged"]]
    h1 = meta.set_index("term").loc["distrust_index_three"]
    h2 = meta.set_index("term").loc["viepol"]
    md = f"""# Stage 9A exploratory country heterogeneity

This post-result extension estimates the same weighted M2 H1-H2a specification
separately in each of the 23 primary countries. Standard errors are clustered by ESS
PSU within country. Stratum identifiers are complete and audited, but the estimator
does not implement a full stratified Taylor linearization; country intervals are
therefore conditional on this documented approximation.

## Direction and evidence categories

{markdown_table(summary)}

![H1 country effects](../figures/stage9_h1_country_ame.png)

![H2 country effects](../figures/stage9_h2_country_ame.png)

Direction is not equated with precision. A positive estimate whose interval includes
zero is compatible with H1/H2 but is not labelled country-level support. Raw p-values
and Benjamini-Hochberg q-values are provided in the country-effect table.

## Random-effects synthesis

{markdown_table(meta_display)}

For representative-political-institution distrust, the random-effects mean is
{h1['estimate']:.3f}, while the prediction interval is {h1['prediction_low']:.3f} to
{h1['prediction_high']:.3f}. For `viepol`, the mean is {h2['estimate']:.3f} and the
prediction interval is {h2['prediction_low']:.3f} to {h2['prediction_high']:.3f}.
Prediction intervals crossing zero indicate that a new comparable country may plausibly
have an association in either direction even when the mean is positive.

![Country shrinkage](../figures/stage9_country_shrinkage.png)

The empirical-Bayes display is secondary: it shows how noisy estimates move toward
the random-effects mean but does not hide the unpooled counter-patterns.

## Model and design diagnostics

All country models converged. {len(diag_flags)} countries have extreme fitted
probabilities or another registered diagnostic flag. Exact model diagnostics are in
`outputs/tables/stage9_country_model_diagnostics.csv`; PSU and stratum diagnostics are
in `outputs/tables/stage9_design_audit.csv`. PSU counts range from
{audit['psu_count'].min()} to {audit['psu_count'].max()}.

## Interpretation

These analyses answer whether country slopes vary, not whether 23 new confirmatory
hypotheses pass separate significance tests. The random-effects mean, prediction
interval, effect directions, FDR values, and sample sizes must be read together. The
accepted Stage 6 common-slope result remains primary.
"""
    (REPORTS / "country_heterogeneity.md").write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Stage 9 country heterogeneity</title><style>body{{font:16px/1.5 system-ui;max-width:1100px;margin:auto;padding:2rem;color:#24303b}}h1,h2{{color:#16324f}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #dbe4ea;padding:.4rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5}}</style></head><body>{rendered}</body></html>"
    (REPORTS / "country_heterogeneity.html").write_text(html, encoding="utf-8")


def main() -> None:
    for directory in (REPORTS, TABLES, FIGURES):
        directory.mkdir(parents=True, exist_ok=True)
    sample, _ = prepare(pd.read_csv(ANALYSIS_BASE, low_memory=False))
    audit = design_audit(sample)
    effects, diagnostics = fit_countries(sample)
    meta, shrunken = synthesize(effects)
    directions = direction_summary(effects)
    audit.to_csv(TABLES / "stage9_design_audit.csv", index=False)
    effects.to_csv(TABLES / "stage9_country_effects.csv", index=False)
    diagnostics.to_csv(TABLES / "stage9_country_model_diagnostics.csv", index=False)
    directions.to_csv(TABLES / "stage9_direction_summary.csv", index=False)
    meta.to_csv(TABLES / "stage9_meta_analysis.csv", index=False)
    shrunken.to_csv(TABLES / "stage9_shrunken_effects.csv", index=False)
    forest_plot(effects, "distrust_index_three", "stage9_h1_country_ame.png")
    forest_plot(effects, "viepol", "stage9_h2_country_ame.png")
    shrinkage_plot(shrunken)
    write_report(effects, diagnostics, directions, meta, audit)
    print("Stage 9A: 23 country models and two random-effects syntheses complete")


if __name__ == "__main__":
    main()
