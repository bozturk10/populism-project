# ruff: noqa: E501
"""Analyze H2b as the incremental contribution of wpestop and votedir."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import markdown
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from populism_project.config import ANALYSIS_BASE, PROCESSED, ROOT
from populism_project.measurement import (
    add_measurements,
    add_model_controls,
    effective_sample_size,
)
from populism_project.modeling import (
    average_marginal_effect,
    cluster_wald_summary,
    counterfactual_average_probability,
    fit_weighted_country_gee,
    joint_wald_f,
    tidy_coefficients,
)

REPORTS = ROOT / "outputs" / "reports"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
MIN_OUTCOME_CELL = 30
FOCAL = ("distrust_index_three", "viepol", "wpestop", "votedir")
ADDED = ("wpestop", "votedir")
CONTROLS = (
    "age_decades_50",
    "C(gndr, Treatment(reference=1))",
    "C(eisced_model, Treatment(reference=4))",
)
CONTROL_FIELDS = ("age_decades_50", "gndr", "eisced_model")
LABELS = {
    "distrust_index_three": "Political distrust",
    "distrust_index_two_plus": "Political distrust (2+ items)",
    "viepol": "People-over-elite priority (viepol)",
    "wpestop": "Unrestricted popular sovereignty (wpestop)",
    "votedir": "Direct-democracy orientation (votedir)",
}


@dataclass(frozen=True)
class Sensitivity:
    code: str
    label: str
    weighted: bool = True
    sparse: bool = False
    alternative_distrust: bool = False
    add_mode: bool = False
    borderline: bool = False


SENSITIVITIES = (
    Sensitivity("H2B", "M3 extended model"),
    Sensitivity("U", "Unweighted", weighted=False),
    Sensitivity("D2", "Distrust index from 2+ items", alternative_distrust=True),
    Sensitivity("MODE", "Add categorical survey mode", add_mode=True),
    Sensitivity("BORD", "Borderline-inclusive classification", borderline=True),
)


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(values.columns) + " |", "|" + "|".join("---" for _ in values.columns) + "|", *["| " + " | ".join(row) + " |" for row in values.to_numpy()]])


def country_formula(focal: tuple[str, ...], *, add_mode: bool = False, outcome: str = "voted_populist", reference: str = "DE") -> str:
    terms = [*focal, *CONTROLS]
    if add_mode:
        terms.append("C(mode, Treatment(reference=1))")
    terms.append(f"C(cntry, Treatment(reference='{reference}'))")
    return f"{outcome} ~ " + " + ".join(terms)


def prepare(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str], pd.DataFrame]:
    eligible = add_model_controls(add_measurements(data.loc[data["analysis_eligible"]].copy()))
    cells = eligible.groupby("cntry")["voted_populist"].agg(["size", "sum"])
    cells["non"] = cells["size"] - cells["sum"]
    primary = sorted(cells.index[cells[["sum", "non"]].min(axis=1).ge(MIN_OUTCOME_CELL)])
    covered = sorted(cells.index)
    frame = eligible.loc[eligible["cntry"].isin(primary) & eligible["anweight"].gt(0)].copy()
    required = [*FOCAL, *CONTROL_FIELDS]
    sample = frame.loc[frame[required].notna().all(axis=1)].copy()
    if len(primary) != 23 or set(primary) != set(sample["cntry"].unique()):
        raise ValueError("H2b must retain the established 23-country primary set")
    return eligible, primary, covered, sample


def cleaning_table(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country, group in data.groupby("cntry", sort=True):
        raw = pd.to_numeric(group["votedir_raw"], errors="coerce")
        rows.append({
            "cntry": country,
            "respondents": len(group),
            "valid_n": int(group["votedir"].notna().sum()),
            "missing_n": int(group["votedir"].isna().sum()),
            "missing_share": float(group["votedir"].isna().mean()),
            "raw_77_refusal": int(raw.eq(77).sum()),
            "raw_88_dont_know": int(raw.eq(88).sum()),
            "raw_99_no_answer": int(raw.eq(99).sum()),
            "valid_min": group["votedir"].min(),
            "valid_max": group["votedir"].max(),
        })
    return pd.DataFrame(rows)


def indicator_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    variables = ["viepol", "wpestop", "votedir"]
    rows = []
    for variable in variables:
        observed = frame[variable].dropna()
        rows.append({
            "variable": variable,
            "concept": LABELS[variable],
            "eligible_n": len(frame),
            "valid_n": len(observed),
            "missing_n": int(frame[variable].isna().sum()),
            "missing_share": float(frame[variable].isna().mean()),
            "mean": float(observed.mean()),
            "sd": float(observed.std()),
            "median": float(observed.median()),
            "min": float(observed.min()),
            "max": float(observed.max()),
            "floor_share_0": float(observed.eq(0).mean()),
            "ceiling_share_10": float(observed.eq(10).mean()),
            "upper_share_8_10": float(observed.ge(8).mean()),
        })
    correlations = frame[variables].corr().rename_axis("variable").reset_index()
    pair_n = frame[variables].notna().astype(int).T @ frame[variables].notna().astype(int)
    pair_n = pair_n.rename_axis("variable").reset_index()
    country_rows = []
    for country, group in frame.groupby("cntry", sort=True):
        for variable in variables:
            observed = group[variable].dropna()
            country_rows.append({
                "cntry": country,
                "variable": variable,
                "eligible_n": len(group),
                "valid_n": len(observed),
                "missing_share": float(group[variable].isna().mean()),
                "mean": float(observed.mean()),
                "sd": float(observed.std()),
                "median": float(observed.median()),
                "min": float(observed.min()),
                "max": float(observed.max()),
                "floor_share_0": float(observed.eq(0).mean()),
                "ceiling_share_10": float(observed.eq(10).mean()),
                "upper_share_8_10": float(observed.ge(8).mean()),
            })
    return pd.DataFrame(rows), correlations.merge(pair_n, on="variable", suffixes=("_r", "_n")), pd.DataFrame(country_rows)


def sample_attrition(frame: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    h2a_required = ["distrust_index_three", "viepol", *CONTROL_FIELDS]
    h2a = frame[h2a_required].notna().all(axis=1)
    h2b_keys = set(sample["respondent_key"])
    rows = []
    for country, group in frame.assign(h2a=h2a).groupby("cntry", sort=True):
        h2a_group = group.loc[group["h2a"]]
        h2b_n = int(h2a_group["respondent_key"].isin(h2b_keys).sum())
        rows.append({
            "cntry": country,
            "classifiable_primary_country": len(group),
            "h2a_complete_n": len(h2a_group),
            "h2b_complete_n": h2b_n,
            "dropped_from_h2a": len(h2a_group) - h2b_n,
            "retained_from_h2a_share": h2b_n / len(h2a_group),
        })
    return pd.DataFrame(rows)


def predictive_metrics(result: object, sample: pd.DataFrame, outcome: str, weights: np.ndarray) -> dict[str, float]:
    predicted = np.clip(np.asarray(result.predict(sample), dtype=float), 1e-12, 1 - 1e-12)
    observed = sample[outcome].to_numpy(dtype=float)
    return {
        "weighted_brier": float(np.average((observed - predicted) ** 2, weights=weights)),
        "weighted_log_loss": float(np.average(-(observed * np.log(predicted) + (1 - observed) * np.log(1 - predicted)), weights=weights)),
    }


def fit_primary(sample: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results = {
        "M2": fit_weighted_country_gee(country_formula(("distrust_index_three", "viepol")), sample),
        "M2 + wpestop": fit_weighted_country_gee(country_formula(("distrust_index_three", "viepol", "wpestop")), sample),
        "M2 + votedir": fit_weighted_country_gee(country_formula(("distrust_index_three", "viepol", "votedir")), sample),
        "M3": fit_weighted_country_gee(country_formula(FOCAL), sample),
    }
    if not all(result.converged for result in results.values()):
        raise RuntimeError("A primary H2b model failed to converge")
    coefficients = pd.concat([
        tidy_coefficients(result, model=name, clusters=sample["cntry"].nunique(), terms=[term for term in FOCAL if term in result.params])
        for name, result in results.items() if name in {"M2", "M3"}
    ], ignore_index=True)
    ame_rows = []
    for name, result in results.items():
        if name not in {"M2", "M3"}:
            continue
        for term in FOCAL:
            if term in result.params:
                ame_rows.append({"model": name, "term": term, **average_marginal_effect(result, term, sample["anweight"], clusters=23)})
    comparison_rows = []
    for name, result in results.items():
        if name not in {"M2", "M3"}:
            continue
        comparison_rows.append({
            "model": name,
            "n": len(sample),
            "countries": 23,
            "parameters": len(result.params),
            "kish_effective_n": effective_sample_size(sample["anweight"]),
            **predictive_metrics(result, sample, "voted_populist", sample["anweight"].to_numpy()),
        })
    joint = pd.DataFrame([{"model": "M3", "terms": "wpestop + votedir", **joint_wald_f(results["M3"], ADDED, clusters=23)}])
    incremental = pd.DataFrame([
        {"comparison": "Add wpestop to M2", **joint_wald_f(results["M2 + wpestop"], ("wpestop",), clusters=23), **predictive_metrics(results["M2 + wpestop"], sample, "voted_populist", sample["anweight"].to_numpy())},
        {"comparison": "Add votedir to M2", **joint_wald_f(results["M2 + votedir"], ("votedir",), clusters=23), **predictive_metrics(results["M2 + votedir"], sample, "voted_populist", sample["anweight"].to_numpy())},
        {"comparison": "Add wpestop after votedir", **joint_wald_f(results["M3"], ("wpestop",), clusters=23), **predictive_metrics(results["M3"], sample, "voted_populist", sample["anweight"].to_numpy())},
        {"comparison": "Add votedir after wpestop", **joint_wald_f(results["M3"], ("votedir",), clusters=23), **predictive_metrics(results["M3"], sample, "voted_populist", sample["anweight"].to_numpy())},
    ])
    return results, coefficients, pd.DataFrame(ame_rows), pd.DataFrame(comparison_rows), joint, incremental


def fit_single_indicator_models(
    sample: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare each H2 indicator separately on the common H2b sample."""
    indicators = ("viepol", "wpestop", "votedir")
    coefficient_frames = []
    ame_rows = []
    comparison_rows = []
    for indicator in indicators:
        model = f"Single: {indicator}"
        result = fit_weighted_country_gee(
            country_formula(("distrust_index_three", indicator)), sample
        )
        if not result.converged:
            raise RuntimeError(f"Single-indicator model failed to converge: {indicator}")
        coefficient_frames.append(
            tidy_coefficients(
                result,
                model=model,
                clusters=sample["cntry"].nunique(),
                terms=(indicator,),
            )
        )
        ame_rows.append(
            {
                "model": model,
                "term": indicator,
                **average_marginal_effect(
                    result,
                    indicator,
                    sample["anweight"],
                    clusters=sample["cntry"].nunique(),
                ),
            }
        )
        comparison_rows.append(
            {
                "model": model,
                "term": indicator,
                "n": len(sample),
                "countries": sample["cntry"].nunique(),
                "parameters": len(result.params),
                **predictive_metrics(
                    result,
                    sample,
                    "voted_populist",
                    sample["anweight"].to_numpy(),
                ),
            }
        )
    return (
        pd.concat(coefficient_frames, ignore_index=True),
        pd.DataFrame(ame_rows),
        pd.DataFrame(comparison_rows),
    )


def m3_indicator_contrasts(result: object, *, clusters: int) -> pd.DataFrame:
    """Directly test pairwise coefficient differences within the joint M3 model."""
    pairs = (("wpestop", "viepol"), ("votedir", "viepol"), ("wpestop", "votedir"))
    covariance = result.cov_params()
    rows = []
    for first, second in pairs:
        estimate = float(result.params[first] - result.params[second])
        variance = float(
            covariance.loc[first, first]
            + covariance.loc[second, second]
            - 2 * covariance.loc[first, second]
        )
        rows.append(
            {
                "contrast": f"{first} - {second}",
                "first": first,
                "second": second,
                "estimate_log_odds_difference": estimate,
                **cluster_wald_summary(
                    estimate, float(np.sqrt(max(variance, 0))), clusters
                ),
            }
        )
    return pd.DataFrame(rows)


def probability_profiles(result: object, sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for term in FOCAL:
        observed = sample[term]
        values = sorted(set([0.0, 5.0, 10.0, float(observed.quantile(0.25)), float(observed.quantile(0.75))]))
        for value in values:
            counterfactual = sample.copy()
            counterfactual[term] = value
            rows.append({"term": term, "value": value, **counterfactual_average_probability(result, counterfactual, sample["anweight"], clusters=23)})
    return pd.DataFrame(rows)


def run_sensitivities(eligible: pd.DataFrame, primary: list[str], covered: list[str]) -> pd.DataFrame:
    rows = []
    eligible = eligible.copy()
    eligible["voted_populist_or_borderline"] = np.maximum(eligible["voted_populist"], eligible["voted_borderline"].fillna(0)).astype(float)
    for check in SENSITIVITIES:
        distrust = "distrust_index_two_plus" if check.alternative_distrust else "distrust_index_three"
        focal = (distrust, "viepol", "wpestop", "votedir")
        countries = covered if check.sparse else primary
        outcome = "voted_populist_or_borderline" if check.borderline else "voted_populist"
        required = [*focal, *CONTROL_FIELDS, *(('mode',) if check.add_mode else ())]
        sample = eligible.loc[eligible["cntry"].isin(countries) & eligible["anweight"].gt(0) & eligible[required].notna().all(axis=1)].copy()
        result = fit_weighted_country_gee(country_formula(focal, add_mode=check.add_mode, outcome=outcome), sample, weight_column="anweight" if check.weighted else None)
        if not result.converged:
            raise RuntimeError(f"Sensitivity {check.code} failed to converge")
        weights = sample["anweight"].to_numpy() if check.weighted else np.ones(len(sample))
        joint = joint_wald_f(result, ADDED, clusters=sample["cntry"].nunique())
        row = {"check": check.code, "label": check.label, "n": len(sample), "countries": sample["cntry"].nunique(), "events": int(sample[outcome].sum()), "weighted": check.weighted, **joint, **predictive_metrics(result, sample, outcome, weights)}
        for term in focal:
            row[f"beta_{term}"] = float(result.params[term])
        rows.append(row)
    return pd.DataFrame(rows)


def country_influence(sample: pd.DataFrame, full_result: object) -> pd.DataFrame:
    rows = []
    for omitted in sorted(sample["cntry"].unique()):
        reduced = sample.loc[sample["cntry"].ne(omitted)].copy()
        reference = "DE" if omitted != "DE" else sorted(reduced["cntry"].unique())[0]
        result = fit_weighted_country_gee(country_formula(FOCAL, reference=reference), reduced)
        joint = joint_wald_f(result, ADDED, clusters=reduced["cntry"].nunique())
        row = {"omitted_country": omitted, "n": len(reduced), **joint}
        for term in FOCAL:
            row[f"beta_{term}"] = float(result.params[term])
            row[f"change_{term}"] = float(result.params[term] - full_result.params[term])
        rows.append(row)
    return pd.DataFrame(rows)


def country_slopes(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    formula = "voted_populist ~ distrust_index_three + viepol + wpestop + votedir + age_decades_50 + C(gndr, Treatment(reference=1)) + C(eisced_model, Treatment(reference=4))"
    for country, group in sample.groupby("cntry", sort=True):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = fit_weighted_country_gee(formula, group, weight_column="anweight", group_column="psu")
        for term in FOCAL:
            rows.append({"cntry": country, "term": term, "estimate_log_odds": float(result.params[term]), "positive": bool(result.params[term] > 0), "converged": bool(result.converged), "n": len(group), "psu_clusters": group["psu"].nunique()})
    return pd.DataFrame(rows)


def make_figure(coefficients: pd.DataFrame) -> None:
    plot = coefficients.copy()
    plot["label"] = plot["term"].map(LABELS) + " — " + plot["model"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    y = np.arange(len(plot))
    ax.errorbar(plot["estimate_log_odds"], y, xerr=[plot["estimate_log_odds"] - plot["conf_low"], plot["conf_high"] - plot["estimate_log_odds"]], fmt="o", capsize=3, color="#1b6ca8")
    ax.axvline(0, color="#333", linestyle="--", linewidth=1)
    ax.set_yticks(y, plot["label"])
    ax.set_xlabel("Log-odds coefficient (95% country-cluster t interval)")
    ax.set_title("H2b nested model comparison on one common sample")
    fig.tight_layout()
    fig.savefig(FIGURES / "h2b_nested_coefficients.png", dpi=180)
    plt.close(fig)


def make_single_indicator_figure(coefficients: pd.DataFrame, sample: pd.DataFrame) -> None:
    """Plot the three same-sample, separate-indicator model estimates."""
    labels = {
        "viepol": "People's views prevail over elites (viepol)",
        "wpestop": "The people's will cannot be stopped (wpestop)",
        "votedir": "Citizens decide through referendums (votedir)",
    }
    order = ["viepol", "wpestop", "votedir"]
    plot = coefficients.set_index("term").loc[order].reset_index()
    y = np.arange(len(plot))
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    ax.errorbar(
        plot["estimate_log_odds"],
        y,
        xerr=[
            plot["estimate_log_odds"] - plot["conf_low"],
            plot["conf_high"] - plot["estimate_log_odds"],
        ],
        fmt="o",
        markersize=7,
        capsize=4,
        color="#1b6ca8",
        ecolor="#1b6ca8",
        linewidth=1.6,
    )
    ax.axvline(0, color="#555555", linestyle="--", linewidth=1)
    ax.set_yticks(y, [labels[term] for term in plot["term"]])
    ax.invert_yaxis()
    ax.set_xlabel("Log-odds coefficient (95% country-clustered t interval)")
    ax.set_title("Separate-indicator associations with populist-party voting")
    ax.text(
        0,
        -0.28,
        f"Separate models on the same sample (N = {len(sample):,}; 23 countries)",
        transform=ax.transAxes,
        fontsize=9,
        color="#555555",
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#d9e1e8", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.subplots_adjust(left=0.43, right=0.97, top=0.82, bottom=0.27)
    fig.savefig(FIGURES / "h2b_single_indicator_coefficients.png", dpi=220)
    plt.close(fig)


def write_cleaning_report(cleaning: pd.DataFrame, attrition: pd.DataFrame, sample: pd.DataFrame) -> None:
    missing = cleaning[["cntry", "respondents", "valid_n", "missing_n", "missing_share", "raw_77_refusal", "raw_88_dont_know", "raw_99_no_answer"]].copy()
    missing["missing_share"] = missing["missing_share"].map(lambda x: f"{x:.1%}")
    attr = attrition.copy()
    attr["retained_from_h2a_share"] = attr["retained_from_h2a_share"].map(lambda x: f"{x:.1%}")
    md = f"""# `votedir` cleaning and H2b sample

`votedir` asks how important it is for democracy that citizens have the final say on the most important political issues by voting directly in referendums. Values 0–10 are valid and retain the ESS direction: 0 means “not at all important” and 10 means “extremely important.” Codes 77 (refusal), 88 (don't know), and 99 (no answer) are recoded to missing from the variable-specific codebook; `votedir_raw` preserves the source value.

## All ESS respondents by country

{markdown_table(missing)}

## H2a-to-H2b complete-case attrition

{markdown_table(attr)}

The extended H2b sample contains {len(sample):,} classifiable voters in {sample['cntry'].nunique()} countries. No established primary-model country is lost; {int(attrition['dropped_from_h2a'].sum()):,} observations are lost relative to the 28,089-person H2a complete-case sample because `wpestop` and/or `votedir` is missing.
"""
    (PROCESSED / "votedir_cleaning_and_h2b_sample.md").write_text(md, encoding="utf-8")


def write_report(tables: dict[str, pd.DataFrame]) -> None:
    coef = tables["coefficients"].copy()
    coef["term"] = coef["term"].map(LABELS)
    coef = coef[["model", "term", "estimate_log_odds", "conf_low", "conf_high", "p_value", "odds_ratio"]].round(4)
    ame = tables["ames"].copy()
    ame["term"] = ame["term"].map(LABELS)
    for column in ["estimate", "conf_low", "conf_high"]:
        ame[column] = (100 * ame[column]).round(3)
    ame = ame[["model", "term", "estimate", "conf_low", "conf_high", "p_value"]].round(4)
    comparison = tables["comparison"].round(5)
    joint = tables["joint"].iloc[0]
    base = tables["coefficients"].query("model == 'M2'").set_index("term")
    extended = tables["coefficients"].query("model == 'M3'").set_index("term")
    change = extended.loc["viepol", "estimate_log_odds"] - base.loc["viepol", "estimate_log_odds"]
    pct = 100 * change / base.loc["viepol", "estimate_log_odds"]
    sensitivities = tables["sensitivities"][["check", "label", "n", "countries", "statistic_f", "numerator_df", "denominator_df", "p_value", "beta_viepol", "beta_wpestop", "beta_votedir"]].round(4)
    influence = tables["influence"]
    worst_joint = influence.loc[influence["p_value"].idxmax()]
    max_changes = {term: influence.loc[influence[f"change_{term}"].abs().idxmax(), ["omitted_country", f"change_{term}"]] for term in FOCAL}
    direction = tables["country_slopes"].groupby("term")["positive"].agg(["sum", "count"])
    incremental = tables["incremental"].round(5)
    single = tables["single_indicator_coefficients"].merge(
        tables["single_indicator_ames"][
            ["model", "term", "estimate", "conf_low", "conf_high"]
        ].rename(
            columns={
                "estimate": "ame",
                "conf_low": "ame_low",
                "conf_high": "ame_high",
            }
        ),
        on=["model", "term"],
    ).merge(
        tables["single_indicator_comparison"],
        on=["model", "term"],
    )
    for column in ("ame", "ame_low", "ame_high"):
        single[column] = 100 * single[column]
    single = single[
        [
            "term",
            "estimate_log_odds",
            "conf_low",
            "conf_high",
            "p_value",
            "ame",
            "ame_low",
            "ame_high",
            "weighted_brier",
            "weighted_log_loss",
        ]
    ].round(5)
    contrasts = tables["m3_indicator_contrasts"].round(5)
    incremental_index = tables["incremental"].set_index("comparison")
    added_source = (
        "mainly `wpestop`: it remains informative after `votedir`, whereas `votedir` is imprecise after `wpestop`"
        if incremental_index.loc["Add wpestop after votedir", "p_value"] < 0.05 <= incremental_index.loc["Add votedir after wpestop", "p_value"]
        else "shared across the two added variables, with no clean single-item attribution"
    )
    profiles = tables["probabilities"]
    profile_5_10 = profiles.loc[profiles["value"].isin([5.0, 10.0])].pivot(index="term", columns="value", values="estimate")
    indicators = tables["indicators"].copy()
    country_ranges = []
    for term, group in tables["country_distributions"].groupby("variable", sort=False):
        mean_low = group.loc[group["mean"].idxmin()]
        mean_high = group.loc[group["mean"].idxmax()]
        ceiling_low = group.loc[group["ceiling_share_10"].idxmin()]
        ceiling_high = group.loc[group["ceiling_share_10"].idxmax()]
        country_ranges.append(
            f"`{term}` country means range from {mean_low['mean']:.2f} ({mean_low['cntry']}) to {mean_high['mean']:.2f} ({mean_high['cntry']}), and score-10 shares from {ceiling_low['ceiling_share_10']:.1%} ({ceiling_low['cntry']}) to {ceiling_high['ceiling_share_10']:.1%} ({ceiling_high['cntry']})"
        )
    indicators["missing_share"] = indicators["missing_share"].map(lambda x: f"{x:.1%}")
    for column in ["mean", "sd", "median", "min", "max", "floor_share_0", "ceiling_share_10", "upper_share_8_10"]:
        indicators[column] = pd.to_numeric(indicators[column]).round(3)
    md = f"""# H2b: additional sovereignty and direct-democracy orientations

## Existing analysis retained

The respondent pipeline uses ESS Round 10 variable-specific codebooks to preserve raw fields and recode only declared special values. Reported voters are linked to the published ESS–Party Facts bridge and PopuList 4.0; the binary outcome is defined only when the selected party can be classified as populist or non-populist. The established primary model uses the complete three-item distrust index (`10 - trstprl`, `10 - trstplt`, `10 - trstprt`), continuous `viepol`, age, gender, education, `anweight`, country fixed intercepts, and country-clustered logistic GEE uncertainty with t-based intervals. Model-specific complete cases are used without imputation. H1 was positive but imprecise (β=0.076, 95% CI −0.150 to 0.303); H2a was positive (β=0.063, 0.036 to 0.090; AME 0.93 percentage points).

## Measurement description

{markdown_table(indicators)}

Pairwise correlations and country distributions are supplied as CSV files. They describe overlap and scale use; they are not evidence that the three variables form a homogeneous scale. `viepol` is treated as the bridge item between a people-over-elite reading and the broader People-Centrism literature, while `wpestop` and `votedir` retain their distinct ESS content. No composite, alpha/omega, EFA, or CFA is used.

Country scale use is visibly non-identical: {'; '.join(country_ranges)}. These contrasts reinforce the need to retain the indicators separately and qualify cross-national comparability.

## Nested comparison

Both models use exactly the same {len(tables['sample']):,} voters in 23 countries. The base model retains distrust, `viepol`, demographics, and country effects; the extended model adds `wpestop` and `votedir` separately.

{markdown_table(comparison)}

GEE does not supply a conventional full-likelihood AIC for this weighted comparison, so AIC/BIC are not used. The same-sample weighted Brier score and log loss are reported as descriptive fit measures; lower values indicate better in-sample prediction.

{markdown_table(coef)}

![H2b coefficients](../figures/h2b_nested_coefficients.png)

The joint cluster-Wald test is F({int(joint['numerator_df'])}, {int(joint['denominator_df'])})={joint['statistic_f']:.3f}, p={joint['p_value']:.4g}. This tests the central H2b question that the two added coefficients are jointly zero. In the extended model, the `viepol` coefficient changes by {change:+.3f} log-odds ({pct:+.1f}% relative to the same-sample base estimate).

The non-preferred one-at-a-time decompositions below are included only to locate the incremental signal, not to select a scale by significance.

{markdown_table(incremental)}

## Same-sample single-indicator comparison

Each model below contains political distrust, one H2 indicator, the same demographic controls, and the same country fixed effects. All models use the identical {len(tables['sample']):,}-person H2b sample. These estimates describe each indicator's overall adjusted association when the other two indicators are omitted; they do not isolate unique contributions or test whether coefficients differ from one another.

{markdown_table(single)}

![Separate-indicator coefficients](../figures/h2b_single_indicator_coefficients.png)

For completeness, the within-M3 pairwise coefficient-difference tests are:

{markdown_table(contrasts)}

## Average marginal effects

{markdown_table(ame)}

The AMEs are average percentage-point changes per one-point increase, not causal effects. Standardizing one score at a time from 5 to 10 changes fitted probability from {profile_5_10.loc['viepol', 5.0]:.1%} to {profile_5_10.loc['viepol', 10.0]:.1%} for `viepol`, {profile_5_10.loc['wpestop', 5.0]:.1%} to {profile_5_10.loc['wpestop', 10.0]:.1%} for `wpestop`, and {profile_5_10.loc['votedir', 5.0]:.1%} to {profile_5_10.loc['votedir', 10.0]:.1%} for `votedir`, holding the observed distribution of all other covariates fixed.

## Sensitivity checks

{markdown_table(sensitivities)}

Leave-one-country-out estimates remain available in the influence table. The least favorable joint-test p-value is {worst_joint['p_value']:.4g} when {worst_joint['omitted_country']} is omitted. The largest absolute coefficient shifts are {', '.join(f"{term}: {row['change_' + term]:+.3f} omitting {row['omitted_country']}" for term, row in max_changes.items())}. Thus the result can be assessed without selecting countries post hoc.

Country-specific extended-model point estimates are positive in {int(direction.loc['viepol','sum'])}/{int(direction.loc['viepol','count'])} countries for `viepol`, {int(direction.loc['wpestop','sum'])}/{int(direction.loc['wpestop','count'])} for `wpestop`, and {int(direction.loc['votedir','sum'])}/{int(direction.loc['votedir','count'])} for `votedir`. These directions diagnose heterogeneity and are not separate confirmatory tests.

## Direct answer to H2b

Yes: `wpestop` and `votedir` jointly provide incremental explanatory information beyond `viepol` under the primary model (F(2, 22)={joint['statistic_f']:.2f}, p={joint['p_value']:.4g}), accompanied by a small improvement in same-sample Brier score and log loss. The `viepol` coefficient falls from {base.loc['viepol','estimate_log_odds']:.3f} to {extended.loc['viepol','estimate_log_odds']:.3f}, a {abs(pct):.1f}% attenuation, and its interval then includes zero. The incremental signal is {added_source}. This does not show that either added item has a causal effect, that their coefficients differ statistically from one another, or that a broader scale is more valid. The narrow H2a operationalization should remain the main-paper measure because it directly matches the people-over-elite claim. H2b should be reported transparently as an exploratory qualification: broadening adds predictive association, chiefly around unrestricted popular sovereignty, but makes the construct less specific by mixing representational, constraint-related, and direct-democratic content.

## Reusable manuscript paragraphs

### Chapter 3 — Methods

As an exploratory extension to H2a, we assessed whether unrestricted popular sovereignty (`wpestop`) and direct-democracy orientation (`votedir`) provided information about populist-party voting beyond the people-over-elite priority measured by `viepol`. We retained the three ESS items as separate 0–10 predictors rather than assuming a homogeneous scale. On a common complete-case sample, we compared the primary weighted country-fixed-intercept logistic GEE with an otherwise identical model adding `wpestop` and `votedir`. Uncertainty was clustered by country, 95% intervals used a t distribution based on the number of country clusters, and the incremental contribution was assessed with a two-degree-of-freedom cluster-Wald F test. All estimates are associational.

### Chapter 4 — Findings

On the common H2b sample, the base `viepol` coefficient was {base.loc['viepol','estimate_log_odds']:.3f} (95% CI {base.loc['viepol','conf_low']:.3f} to {base.loc['viepol','conf_high']:.3f}); after adding the two distinct orientations it was {extended.loc['viepol','estimate_log_odds']:.3f} ({extended.loc['viepol','conf_low']:.3f} to {extended.loc['viepol','conf_high']:.3f}). In the extended model, `wpestop` was {extended.loc['wpestop','estimate_log_odds']:.3f} ({extended.loc['wpestop','conf_low']:.3f} to {extended.loc['wpestop','conf_high']:.3f}) and `votedir` was {extended.loc['votedir','estimate_log_odds']:.3f} ({extended.loc['votedir','conf_low']:.3f} to {extended.loc['votedir','conf_high']:.3f}). Their joint test was F(2, 22)={joint['statistic_f']:.2f}, p={joint['p_value']:.4g}. These results describe incremental explanatory association rather than causal effects.

### Chapter 5 — Conceptual interpretation

The exploratory extension distinguishes statistical gain from conceptual validity. `viepol` directly captures a people-over-elite representational priority and also serves as a bridge to broader People-Centrism accounts; `wpestop` concerns popular sovereignty unconstrained by institutional limits, whereas `votedir` concerns direct-democratic decision making. Adding the latter items may improve explanation of party choice, but it also broadens the construct and makes a single “people-centred” label less specific. We therefore retain the narrow H2a measure for the main claim and present H2b as evidence about related but distinguishable orientations, not as validation of a superior composite scale.
"""
    (REPORTS / "h2b_analysis.md").write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>H2b analysis</title><style>body{{font:16px/1.5 system-ui;max-width:1100px;margin:auto;padding:2rem;color:#24303b}}h1,h2,h3{{color:#16324f}}table{{border-collapse:collapse;width:100%;font-size:.86rem}}th,td{{border:1px solid #dbe4ea;padding:.4rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5}}</style></head><body>{rendered}</body></html>"
    (REPORTS / "h2b_analysis.html").write_text(html, encoding="utf-8")


def main() -> None:
    for directory in (PROCESSED, REPORTS, TABLES, FIGURES):
        directory.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(ANALYSIS_BASE, low_memory=False)
    eligible, primary, covered, sample = prepare(raw)
    primary_frame = eligible.loc[eligible["cntry"].isin(primary) & eligible["anweight"].gt(0)].copy()
    cleaning = cleaning_table(raw)
    indicators, correlations, country_distributions = indicator_tables(primary_frame)
    attrition = sample_attrition(primary_frame, sample)
    results, coefficients, ames, comparison, joint, incremental = fit_primary(sample)
    single_coefficients, single_ames, single_comparison = fit_single_indicator_models(
        sample
    )
    contrasts = m3_indicator_contrasts(results["M3"], clusters=23)
    probabilities = probability_profiles(results["M3"], sample)
    sensitivities = run_sensitivities(eligible, primary, covered)
    influence = country_influence(sample, results["M3"])
    slopes = country_slopes(sample)
    tables = {
        "sample": sample,
        "indicators": indicators,
        "correlations": correlations,
        "country_distributions": country_distributions,
        "attrition": attrition,
        "coefficients": coefficients,
        "ames": ames,
        "comparison": comparison,
        "joint": joint,
        "incremental": incremental,
        "single_indicator_coefficients": single_coefficients,
        "single_indicator_ames": single_ames,
        "single_indicator_comparison": single_comparison,
        "m3_indicator_contrasts": contrasts,
        "probabilities": probabilities,
        "sensitivities": sensitivities,
        "influence": influence,
        "country_slopes": slopes,
    }
    outputs = {
        "indicators": "h2b_indicator_summary.csv",
        "correlations": "h2b_pairwise_correlations.csv",
        "country_distributions": "h2b_country_distributions.csv",
        "attrition": "h2b_sample_attrition.csv",
        "coefficients": "h2b_model_coefficients.csv",
        "ames": "h2b_average_marginal_effects.csv",
        "comparison": "h2b_model_comparison.csv",
        "joint": "h2b_joint_test.csv",
        "incremental": "h2b_incremental_decomposition.csv",
        "single_indicator_coefficients": "h2b_single_indicator_coefficients.csv",
        "single_indicator_ames": "h2b_single_indicator_ames.csv",
        "single_indicator_comparison": "h2b_single_indicator_comparison.csv",
        "m3_indicator_contrasts": "h2b_m3_indicator_contrasts.csv",
        "probabilities": "h2b_predicted_probabilities.csv",
        "sensitivities": "h2b_sensitivity_checks.csv",
        "influence": "h2b_country_influence.csv",
        "country_slopes": "h2b_country_slopes.csv",
    }
    for key, filename in outputs.items():
        tables[key].to_csv(TABLES / filename, index=False)
    cleaning.to_csv(PROCESSED / "votedir_cleaning_by_country.csv", index=False)
    sample[["respondent_key", "cntry"]].to_csv(PROCESSED / "h2b_complete_case_keys.csv", index=False)
    write_cleaning_report(cleaning, attrition, sample)
    make_figure(coefficients)
    make_single_indicator_figure(single_coefficients, sample)
    write_report(tables)
    print(f"H2b complete: {len(sample):,} voters; {len(primary)} primary countries; joint F={joint.iloc[0]['statistic_f']:.3f}, p={joint.iloc[0]['p_value']:.4g}")


if __name__ == "__main__":
    main()
