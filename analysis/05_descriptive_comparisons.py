# ruff: noqa: E501
"""Build reproducible Stage 5 descriptive H1-H2 comparisons."""

from __future__ import annotations

import markdown
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from populism_project.config import ANALYSIS_BASE, ROOT
from populism_project.descriptives import (
    descriptive_stats,
    difference_stats,
    score_band_shares,
)
from populism_project.measurement import (
    DOMAIN_TRUST_ITEMS,
    PRIMARY_CONTROLS,
    add_measurements,
    add_model_controls,
)

REPORTS = ROOT / "outputs" / "reports"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"
MIN_OUTCOME_CELL = 30

MEASURES = {
    "distrust_index_three": "Political distrust index",
    "viepol": "People's views should prevail (viepol)",
}
GROUPS = {0.0: "Non-populist-party voters", 1.0: "Populist-party voters"}
DOMAIN_LABELS = {
    "distrust_prl": "Parliament",
    "distrust_plt": "Politicians",
    "distrust_prt": "Political parties",
    "distrust_lgl": "Legal system",
    "distrust_plc": "Police",
    "distrust_ep": "European Parliament",
    "distrust_un": "United Nations",
    "distrust_sci": "Scientists",
    "distrust_people": "Other people",
}


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    header = "| " + " | ".join(values.columns) + " |"
    divider = "|" + "|".join("---" for _ in values.columns) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in values.to_numpy()]
    return "\n".join([header, divider, *rows])


def prepare_samples(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return eligible voters and the accepted common H2 descriptive sample."""
    eligible = add_model_controls(
        add_measurements(data.loc[data["analysis_eligible"]].copy())
    )
    cells = eligible.groupby("cntry")["voted_populist"].agg(["size", "sum"])
    cells["non_populist"] = cells["size"] - cells["sum"]
    primary_countries = cells.index[
        cells[["sum", "non_populist"]].min(axis=1).ge(MIN_OUTCOME_CELL)
    ]
    common_mask = (
        eligible["cntry"].isin(primary_countries)
        & eligible["anweight"].gt(0)
        & eligible[["distrust_index_three", "viepol", *PRIMARY_CONTROLS]]
        .notna()
        .all(axis=1)
    )
    common = eligible.loc[common_mask].copy()
    if len(common) != 28_089 or common["cntry"].nunique() != 23:
        raise ValueError("Stage 5 common sample must have 28,089 voters in 23 countries")
    return eligible, common


def summarize_group(
    group: pd.DataFrame, measure: str, weighting: str
) -> dict[str, float | int]:
    weights = group["anweight"] if weighting == "weighted" else None
    return descriptive_stats(group[measure], weights)


def build_tables(
    eligible: pd.DataFrame, common: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    summary_rows = []
    contrast_rows = []
    distribution_rows = []
    for measure, label in MEASURES.items():
        for weighting in ["weighted", "unweighted"]:
            stats_by_group = {}
            for group_value, group_label in GROUPS.items():
                group = common.loc[common["voted_populist"].eq(group_value)]
                stats = summarize_group(group, measure, weighting)
                stats_by_group[group_value] = stats
                summary_rows.append(
                    {
                        "measure": measure,
                        "measure_label": label,
                        "weighting": weighting,
                        "voting_group": group_label,
                        **stats,
                    }
                )
                bands = score_band_shares(
                    group[measure],
                    group["anweight"] if weighting == "weighted" else None,
                )
                for row in bands.to_dict("records"):
                    distribution_rows.append(
                        {
                            "measure": measure,
                            "measure_label": label,
                            "weighting": weighting,
                            "voting_group": group_label,
                            **row,
                        }
                    )
            contrast_rows.append(
                {
                    "measure": measure,
                    "measure_label": label,
                    "weighting": weighting,
                    "contrast": "Populist minus non-populist",
                    **difference_stats(stats_by_group[1.0], stats_by_group[0.0]),
                }
            )

    country_rows = []
    for country, country_data in common.groupby("cntry", sort=True):
        for measure, label in MEASURES.items():
            for weighting in ["weighted", "unweighted"]:
                group_stats = {}
                for group_value in GROUPS:
                    group = country_data.loc[
                        country_data["voted_populist"].eq(group_value)
                    ]
                    group_stats[group_value] = summarize_group(
                        group, measure, weighting
                    )
                country_rows.append(
                    {
                        "cntry": country,
                        "measure": measure,
                        "measure_label": label,
                        "weighting": weighting,
                        "non_populist_n": group_stats[0.0]["n"],
                        "populist_n": group_stats[1.0]["n"],
                        "non_populist_mean": group_stats[0.0]["mean"],
                        "populist_mean": group_stats[1.0]["mean"],
                        **difference_stats(group_stats[1.0], group_stats[0.0]),
                    }
                )
    country_contrasts = pd.DataFrame(country_rows)

    within_country_rows = []
    for (measure, label, weighting), group in country_contrasts.groupby(
        ["measure", "measure_label", "weighting"], sort=False
    ):
        within_country_rows.append(
            {
                "measure": measure,
                "measure_label": label,
                "weighting": weighting,
                "countries": len(group),
                "countries_positive_difference": int(group["difference"].gt(0).sum()),
                "equal_country_mean_difference": group["difference"].mean(),
                "median_country_difference": group["difference"].median(),
                "min_country_difference": group["difference"].min(),
                "max_country_difference": group["difference"].max(),
            }
        )

    if len(DOMAIN_TRUST_ITEMS) != len(DOMAIN_LABELS):
        raise ValueError("Trust-domain labels must cover every retained domain")
    domain_columns = list(DOMAIN_LABELS)
    domain_mask = (
        eligible["cntry"].isin(common["cntry"].unique())
        & eligible["anweight"].gt(0)
        & eligible[domain_columns].notna().all(axis=1)
    )
    domain_sample = eligible.loc[domain_mask]
    domain_rows = []
    for measure, label in DOMAIN_LABELS.items():
        for weighting in ["weighted", "unweighted"]:
            group_stats = {}
            for group_value in GROUPS:
                group = domain_sample.loc[
                    domain_sample["voted_populist"].eq(group_value)
                ]
                group_stats[group_value] = summarize_group(
                    group, measure, weighting
                )
            domain_rows.append(
                {
                    "measure": measure,
                    "measure_label": label,
                    "weighting": weighting,
                    "common_n": len(domain_sample),
                    "non_populist_mean": group_stats[0.0]["mean"],
                    "populist_mean": group_stats[1.0]["mean"],
                    **difference_stats(group_stats[1.0], group_stats[0.0]),
                }
            )

    return {
        "group_summaries": pd.DataFrame(summary_rows),
        "group_distributions": pd.DataFrame(distribution_rows),
        "pooled_contrasts": pd.DataFrame(contrast_rows),
        "country_contrasts": country_contrasts,
        "within_country_summary": pd.DataFrame(within_country_rows),
        "domain_group_contrasts": pd.DataFrame(domain_rows),
    }


def make_figures(tables: dict[str, pd.DataFrame]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {"weighted": "#d95f02", "unweighted": "#1b9e77"}

    summaries = tables["group_summaries"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, (measure, label) in zip(axes, MEASURES.items(), strict=True):
        panel = summaries[summaries["measure"].eq(measure)]
        for weighting, offset in [("weighted", -0.12), ("unweighted", 0.12)]:
            rows = panel[panel["weighting"].eq(weighting)].set_index("voting_group")
            ordered = rows.loc[list(GROUPS.values())]
            x = np.arange(2) + offset
            ax.errorbar(
                x,
                ordered["mean"],
                yerr=[
                    ordered["mean"] - ordered["ci_low"],
                    ordered["ci_high"] - ordered["mean"],
                ],
                fmt="o",
                capsize=4,
                color=colors[weighting],
                label=weighting.title(),
            )
        ax.set_xticks(np.arange(2), ["Non-populist", "Populist"])
        ax.set(title=label, ylabel="Mean score (0-10)", ylim=(0, 10))
        ax.legend()
    fig.suptitle("H1-H2 means by reported party-vote group")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage5_group_means.png", dpi=180)
    plt.close(fig)

    distributions = tables["group_distributions"].query("weighting == 'weighted'")
    band_colors = {"0-3": "#4575b4", "4-7": "#ffffbf", "8-10": "#d73027"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True)
    for ax, (measure, label) in zip(axes, MEASURES.items(), strict=True):
        panel = distributions[distributions["measure"].eq(measure)]
        wide = panel.pivot(index="voting_group", columns="score_band", values="share")
        wide = wide.loc[list(GROUPS.values()), ["0-3", "4-7", "8-10"]]
        left = pd.Series(0.0, index=wide.index)
        for band in wide.columns:
            ax.barh(
                ["Non-populist", "Populist"],
                wide[band] * 100,
                left=left * 100,
                color=band_colors[band],
                label=band,
            )
            left += wide[band]
        ax.set(title=label, xlabel="Weighted respondents (%)", xlim=(0, 100))
        ax.legend().remove()
    fig.suptitle("Weighted H1-H2 score distributions by voting group")
    fig.legend(
        handles=[Patch(color=band_colors[band], label=band) for band in band_colors],
        title="Score band",
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, -0.01),
    )
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(FIGURES / "stage5_group_distributions.png", dpi=180)
    plt.close(fig)

    country = tables["country_contrasts"].query("weighting == 'weighted'")
    fig, axes = plt.subplots(1, 2, figsize=(13, 9))
    for ax, (measure, label) in zip(axes, MEASURES.items(), strict=True):
        panel = country[country["measure"].eq(measure)].sort_values("difference")
        y = np.arange(len(panel))
        ax.errorbar(
            panel["difference"],
            y,
            xerr=[
                panel["difference"] - panel["ci_low"],
                panel["ci_high"] - panel["difference"],
            ],
            fmt="o",
            capsize=2,
            color="#4c78a8",
            markersize=4,
        )
        ax.axvline(0, color="#333333", linewidth=1)
        ax.set_yticks(y, panel["cntry"])
        ax.set(
            title=label,
            xlabel="Populist minus non-populist mean",
            ylabel="Country",
        )
    fig.suptitle("Weighted within-country descriptive contrasts")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage5_country_contrasts.png", dpi=180)
    plt.close(fig)

    domain = tables["domain_group_contrasts"].query("weighting == 'weighted'")
    domain = domain.sort_values("difference")
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = [
        "#d95f02" if measure in {"distrust_prl", "distrust_plt", "distrust_prt"}
        else "#4c78a8"
        for measure in domain["measure"]
    ]
    ax.barh(
        domain["measure_label"],
        domain["difference"],
        xerr=[
            domain["difference"] - domain["ci_low"],
            domain["ci_high"] - domain["difference"],
        ],
        color=colors,
        capsize=3,
    )
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set(
        xlabel="Populist minus non-populist weighted mean",
        ylabel="Trust domain (all reverse-coded)",
        title="Descriptive distrust gaps across domains",
    )
    ax.legend(
        handles=[
            Patch(color="#d95f02", label="H1 political item"),
            Patch(color="#4c78a8", label="Comparison domain"),
        ],
        loc="lower right",
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "stage5_domain_contrasts.png", dpi=180)
    plt.close(fig)


def build_report(tables: dict[str, pd.DataFrame]) -> tuple:
    summaries = tables["group_summaries"].copy()
    summaries = summaries[
        [
            "measure_label",
            "weighting",
            "voting_group",
            "n",
            "effective_n",
            "mean",
            "sd",
            "ci_low",
            "ci_high",
        ]
    ].round(3)
    pooled = tables["pooled_contrasts"].copy()
    pooled = pooled[
        ["measure_label", "weighting", "difference", "ci_low", "ci_high"]
    ].round(3)
    within = tables["within_country_summary"].copy()
    within = within[
        [
            "measure_label",
            "weighting",
            "countries",
            "countries_positive_difference",
            "equal_country_mean_difference",
            "median_country_difference",
            "min_country_difference",
            "max_country_difference",
        ]
    ].round(3)
    domain = tables["domain_group_contrasts"].copy()
    domain = domain.query("weighting == 'weighted'")[
        [
            "measure_label",
            "common_n",
            "non_populist_mean",
            "populist_mean",
            "difference",
            "ci_low",
            "ci_high",
        ]
    ].round(3)

    weighted = tables["pooled_contrasts"].query("weighting == 'weighted'")
    distrust_gap = weighted.loc[
        weighted["measure"].eq("distrust_index_three"), "difference"
    ].item()
    viepol_gap = weighted.loc[weighted["measure"].eq("viepol"), "difference"].item()
    country_weighted = tables["within_country_summary"].query(
        "weighting == 'weighted'"
    )
    distrust_positive = country_weighted.loc[
        country_weighted["measure"].eq("distrust_index_three"),
        "countries_positive_difference",
    ].item()
    viepol_positive = country_weighted.loc[
        country_weighted["measure"].eq("viepol"),
        "countries_positive_difference",
    ].item()
    weighted_country = tables["country_contrasts"].query("weighting == 'weighted'")
    distrust_negative = ", ".join(
        weighted_country.loc[
            weighted_country["measure"].eq("distrust_index_three")
            & weighted_country["difference"].lt(0),
            "cntry",
        ]
    )
    viepol_negative = ", ".join(
        weighted_country.loc[
            weighted_country["measure"].eq("viepol")
            & weighted_country["difference"].lt(0),
            "cntry",
        ]
    )

    md = f"""# Stage 5 descriptive H1-H2 comparisons

This report describes the accepted common H2 model sample: **28,089 classifiable
voters in 23 countries**. It contains no regression model and does not establish
independent, adjusted, or causal associations.

The project owner accepted all Stage 5 outputs and interpretations on 2026-09-08;
they remain explicitly available for re-verification in a later session.

## Pooled group summaries

{markdown_table(summaries)}

![Group means](../figures/stage5_group_means.png)

Approximate 95% intervals are mean ± 1.96 standard errors. Weighted standard errors
use the Kish effective sample size; they do not yet incorporate the full complex
survey design or the country-fixed-effect model. They are descriptive guides only.

## Pooled differences

{markdown_table(pooled)}

In the weighted pooled comparison, populist-party voters score **{distrust_gap:.2f}
points higher** on political distrust and **{viepol_gap:.2f} points higher** on
`viepol` than non-populist-party voters. These pooled gaps combine within- and
between-country composition and therefore are not the final H1-H2 estimates.

## Score distributions

![Weighted score distributions](../figures/stage5_group_distributions.png)

The source table reports both weighted and unweighted shares in descriptive bands
0-3, 4-7, and 8-10. These bands are visual summaries, not regression cutoffs.

## Within-country contrasts

{markdown_table(within)}

![Country contrasts](../figures/stage5_country_contrasts.png)

The weighted mean difference is positive in **{distrust_positive} of 23 countries**
for distrust and **{viepol_positive} of 23 countries** for `viepol`. Variation in
country gaps is expected and is shown rather than hidden; Stage 6 will estimate the
pre-specified country-adjusted associations.

The raw distrust difference is negative in {distrust_negative}; the raw `viepol`
difference is negative in {viepol_negative}. Poland and Hungary are especially clear
counter-patterns for distrust. Stage 5 therefore does not support a claim that the
pooled descriptive relationship is uniform across national party systems.

Exact country means, differences, and approximate intervals are in
`outputs/tables/stage5_country_contrasts.csv`.

## Trust-domain specificity

{markdown_table(domain)}

![Trust-domain contrasts](../figures/stage5_domain_contrasts.png)

This comparison uses one common complete-case sample across all nine reverse-coded
trust domains so differences in domain gaps are not caused by changing respondents.
The orange bars are the H1 representative-political items; all other domains remain
exploratory specificity checks outside the index. The gaps for the European
Parliament and legal system are larger than the gaps for politicians or political
parties. The group difference is therefore not unique to the H1 domain, even though
the accepted index remains theoretically focused on representative national politics.

## Interpretation boundary

Stage 5 shows whether the raw descriptive direction is compatible with H1 and H2 and
whether it appears across countries. It does not test whether `viepol` contributes
beyond distrust or whether either association persists after controls. Those are
Stage 6 questions under the already accepted specification.
"""
    md_path = REPORTS / "descriptive_comparisons.md"
    md_path.write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Stage 5 descriptive comparisons</title><style>body{{font:16px/1.5 system-ui;max-width:1100px;margin:auto;padding:2rem;color:#24303b}}h1,h2{{color:#16324f}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}th,td{{border:1px solid #dbe4ea;padding:.45rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5;padding:.1rem .25rem}}</style></head><body>{rendered}</body></html>"""
    html_path = REPORTS / "descriptive_comparisons.html"
    html_path.write_text(html, encoding="utf-8")
    return md_path, html_path


def main() -> None:
    for directory in (REPORTS, FIGURES, TABLES):
        directory.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(ANALYSIS_BASE, low_memory=False)
    eligible, common = prepare_samples(data)
    tables = build_tables(eligible, common)
    for name, table in tables.items():
        table.to_csv(TABLES / f"stage5_{name}.csv", index=False)
    make_figures(tables)
    md_path, html_path = build_report(tables)
    print(f"Stage 5 sample: {len(common):,} voters in {common['cntry'].nunique()} countries")
    print(f"Wrote {md_path.relative_to(ROOT)}")
    print(f"Wrote {html_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
