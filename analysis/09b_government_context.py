# ruff: noqa: E501
"""Build and analyse the exploratory populist government/opposition context."""

from __future__ import annotations

import sqlite3

import markdown
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from populism_project.config import ANALYSIS_BASE, PARTY_MAPPING, POPULIST, ROOT
from populism_project.measurement import add_measurements, add_model_controls
from populism_project.modeling import (
    cluster_wald_summary,
    fit_weighted_country_gee,
    tidy_coefficients,
)

PARLGOV = ROOT / "data" / "raw" / "ParlGov" / "parlgov-stable.db"
REPORTS = ROOT / "outputs" / "reports"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
PROCESSED = ROOT / "data" / "processed"
PRIMARY_CONTROLS = ["age_decades_50", "gndr", "eisced_model"]


def markdown_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(values.columns) + " |", "|" + "|".join("---" for _ in values.columns) + "|", *["| " + " | ".join(row) + " |" for row in values.to_numpy()]])


def load_parlgov() -> dict[str, pd.DataFrame]:
    connection = sqlite3.connect(PARLGOV)
    try:
        return {table: pd.read_sql_query(f"SELECT * FROM {table}", connection) for table in ["country", "cabinet", "cabinet_party", "party"]}
    finally:
        connection.close()


def build_context(mapping: pd.DataFrame, pg: dict[str, pd.DataFrame], populist: pd.DataFrame) -> pd.DataFrame:
    elections = mapping[["cntry", "country", "election_date"]].dropna().drop_duplicates()
    rows = []
    for record in elections.itertuples(index=False):
        country_match = pg["country"].loc[pg["country"]["name_short"].eq(record.country)]
        if len(country_match) != 1:
            rows.append({"cntry": record.cntry, "country_iso3": record.country, "election_date": record.election_date, "status": "country_not_in_parlgov"})
            continue
        country = country_match.iloc[0]
        cabinets = pg["cabinet"].loc[(pg["cabinet"]["country_id"].eq(country["id"])) & (pg["cabinet"]["start_date"].lt(record.election_date))].sort_values("start_date")
        if cabinets.empty:
            rows.append({"cntry": record.cntry, "country_iso3": record.country, "election_date": record.election_date, "status": "no_pre_election_cabinet"})
            continue
        immediate = cabinets.iloc[-1]
        partisan = cabinets.loc[cabinets["caretaker"].fillna(0).eq(0)].iloc[-1] if bool(immediate["caretaker"]) else immediate
        cabinet_parties = set(pg["cabinet_party"].loc[pg["cabinet_party"]["cabinet_id"].eq(partisan["id"]), "party_id"].dropna().astype(int))
        year = int(str(record.election_date)[:4])
        active = populist.loc[populist["country_name"].eq(country["name"]) & populist["populist"].eq(1) & populist["populist_start"].le(year) & populist["populist_end"].ge(year)]
        active_ids = set(pd.to_numeric(active["parlgov_id"], errors="coerce").dropna().astype(int))
        incumbent_ids = sorted(cabinet_parties & active_ids)
        incumbent_names = pg["party"].loc[pg["party"]["id"].isin(incumbent_ids), "name_short"].astype(str).tolist()
        rows.append({"cntry": record.cntry, "country_iso3": record.country, "election_date": record.election_date, "status": "matched", "immediate_cabinet_id": int(immediate["id"]), "immediate_cabinet_name": immediate["name"], "immediate_cabinet_start": immediate["start_date"], "immediate_caretaker": bool(immediate["caretaker"]), "partisan_cabinet_id": int(partisan["id"]), "partisan_cabinet_name": partisan["name"], "partisan_cabinet_start": partisan["start_date"], "populist_in_pre_election_government": bool(incumbent_ids), "incumbent_populist_parlgov_ids": ";".join(map(str, incumbent_ids)), "incumbent_populist_parties": ";".join(incumbent_names), "source": "ParlGov 2024 stable V1; DOI 10.7910/DVN/2VZ5ZC"})
    result = pd.DataFrame(rows)
    result["matched_priority"] = result["status"].eq("matched").astype(int)
    result = result.sort_values(["cntry", "matched_priority"], ascending=[True, False])
    return result.drop_duplicates("cntry").drop(columns="matched_priority")


def party_crosswalk(mapping: pd.DataFrame, populist: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    lookup = populist[["partyfacts_id", "parlgov_id"]].copy()
    lookup["partyfacts_id"] = pd.to_numeric(lookup["partyfacts_id"], errors="coerce")
    lookup["parlgov_id"] = pd.to_numeric(lookup["parlgov_id"], errors="coerce")
    lookup = lookup.dropna().drop_duplicates("partyfacts_id")
    rows = mapping.loc[mapping["final_populist"].eq(1), ["cntry", "ess_variable", "ess_party_code", "ess_party_label", "partyfacts_id", "manual_target_partyfacts_id", "populist_parlgov_id", "election_date"]].drop_duplicates().copy()
    rows["link_partyfacts_id"] = rows["manual_target_partyfacts_id"].fillna(rows["partyfacts_id"])
    rows = rows.merge(lookup.rename(columns={"partyfacts_id": "link_partyfacts_id", "parlgov_id": "lookup_parlgov_id"}), on="link_partyfacts_id", how="left", validate="many_to_one")
    rows["resolved_parlgov_id"] = pd.to_numeric(rows["populist_parlgov_id"], errors="coerce").fillna(rows["lookup_parlgov_id"])
    incumbent = context.set_index("cntry")["incumbent_populist_parlgov_ids"].fillna("").map(lambda value: {int(item) for item in str(value).split(";") if item})
    rows["government_status"] = rows.apply(lambda row: "unresolved" if pd.isna(row["resolved_parlgov_id"]) else ("incumbent_populist" if int(row["resolved_parlgov_id"]) in incumbent.get(row["cntry"], set()) else "opposition_populist"), axis=1)
    rows["link_method"] = np.where(rows["populist_parlgov_id"].notna(), "existing_PopuList_mapping", np.where(rows["lookup_parlgov_id"].notna(), "PopuList_partyfacts_id_to_parlgov_id", "unresolved"))
    return rows.sort_values(["cntry", "ess_variable", "ess_party_code"])


def prepare_model_data(data: pd.DataFrame, context: pd.DataFrame, crosswalk: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    eligible = add_model_controls(add_measurements(data.loc[data["analysis_eligible"]].copy()))
    cells = eligible.groupby("cntry")["voted_populist"].agg(["size", "sum"])
    cells["non"] = cells["size"] - cells["sum"]
    countries = sorted(cells.index[cells[["sum", "non"]].min(axis=1).ge(30)])
    eligible = eligible.merge(context[["cntry", "populist_in_pre_election_government"]], on="cntry", how="left", validate="many_to_one")
    keys = ["cntry", "ess_variable", "ess_party_code"]
    eligible = eligible.merge(crosswalk[[*keys, "government_status"]], on=keys, how="left", validate="many_to_one")
    eligible["vote_type"] = np.where(eligible["voted_populist"].eq(0), "non_populist", eligible["government_status"].fillna("populist_unresolved"))
    sample = eligible.loc[eligible["cntry"].isin(countries) & eligible["anweight"].gt(0) & eligible[["distrust_index_three", "viepol", *PRIMARY_CONTROLS, "populist_in_pre_election_government"]].notna().all(axis=1)].copy()
    return sample, countries


def context_model(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    interaction_formula = "distrust_index_three:populist_in_pre_election_government"
    interaction = f"{interaction_formula}[T.True]"
    formula = f"voted_populist ~ distrust_index_three + {interaction_formula} + viepol + age_decades_50 + C(gndr, Treatment(reference=1)) + C(eisced_model, Treatment(reference=4)) + C(cntry, Treatment(reference='DE'))"
    result = fit_weighted_country_gee(formula, sample, weight_column="anweight", group_column="cntry")
    terms = ["distrust_index_three", interaction, "viepol"]
    effects = tidy_coefficients(result, model="context_interaction", clusters=sample["cntry"].nunique(), terms=terms)
    covariance = result.cov_params()
    base = float(result.params["distrust_index_three"])
    delta = float(result.params[interaction])
    opposition = cluster_wald_summary(base, float(np.sqrt(covariance.loc["distrust_index_three", "distrust_index_three"])), 23)
    government_variance = float(covariance.loc["distrust_index_three", "distrust_index_three"] + covariance.loc[interaction, interaction] + 2 * covariance.loc["distrust_index_three", interaction])
    government = cluster_wald_summary(base + delta, float(np.sqrt(max(government_variance, 0))), 23)
    slopes = pd.DataFrame([{"context": "No populist in pre-election government", "estimate": base, **opposition}, {"context": "Populist in pre-election government", "estimate": base + delta, **government}])
    return effects, slopes


def context_influence(sample: pd.DataFrame) -> pd.DataFrame:
    interaction_formula = "distrust_index_three:populist_in_pre_election_government"
    interaction = f"{interaction_formula}[T.True]"
    rows = []
    for omitted in sorted(sample["cntry"].unique()):
        reduced = sample.loc[sample["cntry"].ne(omitted)].copy()
        reference = "DE" if omitted != "DE" else sorted(reduced["cntry"].unique())[0]
        formula = f"voted_populist ~ distrust_index_three + {interaction_formula} + viepol + age_decades_50 + C(gndr, Treatment(reference=1)) + C(eisced_model, Treatment(reference=4)) + C(cntry, Treatment(reference='{reference}'))"
        result = fit_weighted_country_gee(formula, reduced, weight_column="anweight", group_column="cntry")
        row = tidy_coefficients(result, model=omitted, clusters=reduced["cntry"].nunique(), terms=[interaction]).iloc[0]
        rows.append({"omitted_country": omitted, "interaction_estimate": row["estimate_log_odds"], "conf_low": row["conf_low"], "conf_high": row["conf_high"], "p_value": row["p_value"], "converged": bool(result.converged)})
    return pd.DataFrame(rows)


def vote_type_tables(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = sample.groupby(["cntry", "vote_type"], dropna=False).size().unstack(fill_value=0).reset_index()
    for column in ["non_populist", "incumbent_populist", "opposition_populist", "unresolved", "populist_unresolved"]:
        if column not in cells:
            cells[column] = 0
    summaries = []
    for vote_type, group in sample.groupby("vote_type"):
        weights = group["anweight"]
        summaries.append({"vote_type": vote_type, "n": len(group), "countries": group["cntry"].nunique(), "weighted_mean_distrust": np.average(group["distrust_index_three"], weights=weights), "weighted_mean_viepol": np.average(group["viepol"], weights=weights)})
    return cells, pd.DataFrame(summaries)


def make_figure(slopes: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    y = np.arange(len(slopes))
    ax.errorbar(slopes["estimate"], y, xerr=[slopes["estimate"] - slopes["conf_low"], slopes["conf_high"] - slopes["estimate"]], fmt="o", capsize=4, color="#1b6ca8")
    ax.axvline(0, color="#333", linestyle="--")
    ax.set_yticks(y, slopes["context"])
    ax.set_xlabel("Distrust log-odds slope (95% country-cluster-t interval)")
    ax.set_title("Exploratory H1 slope by pre-election\npopulist-government context")
    fig.tight_layout()
    fig.savefig(FIGURES / "stage9_government_context_slopes.png", dpi=180)
    plt.close(fig)


def make_country_context_figure(country_context: pd.DataFrame) -> None:
    panels = [
        (False, "No populist party in government"),
        (True, "Populist party in government"),
    ]
    colors = {False: "#2878b5", True: "#d95f02"}
    limit = 100 * max(country_context["ame_high"].abs().max(), country_context["ame_low"].abs().max())
    fig, axes = plt.subplots(1, 2, figsize=(12, 7.2), sharex=True)
    for ax, (status, title) in zip(axes, panels, strict=True):
        subset = country_context.loc[
            country_context["populist_in_pre_election_government"].eq(status)
        ].sort_values("ame")
        y = np.arange(len(subset))
        ax.hlines(
            y,
            100 * subset["ame_low"],
            100 * subset["ame_high"],
            color=colors[status],
            alpha=0.55,
            linewidth=2,
        )
        ax.scatter(100 * subset["ame"], y, color=colors[status], s=52, zorder=3)
        ax.axvline(0, color="#333333", linestyle="--", linewidth=1.2)
        ax.set_yticks(y, subset["cntry"])
        ax.set_title(f"{title}\n({len(subset)} countries)", color=colors[status])
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlim(-limit * 1.05, limit * 1.05)
    fig.suptitle(
        "Political distrust and populist voting by country context\n"
        "Each dot is one country",
        fontsize=16,
    )
    fig.supxlabel(
        "Effect of a 1-point increase in distrust on predicted populist-vote probability "
        "(percentage points)",
        y=0.06,
    )
    fig.text(
        0.5,
        0.02,
        "Left of dashed line = negative relationship  |  Right = positive relationship  |  Lines = 95% confidence intervals",
        ha="center",
        color="#555555",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.13, 1, 0.91])
    fig.savefig(FIGURES / "stage9_country_effects_by_government_context.png", dpi=180)
    plt.close(fig)


def make_context_colored_forest(country_context: pd.DataFrame) -> None:
    plot = country_context.sort_values("ame")
    colors = {False: "#2878b5", True: "#d95f02"}
    labels = {
        False: "No populist party in government",
        True: "Populist party in government",
    }
    fig, ax = plt.subplots(figsize=(9, 9))
    for index, (_, row) in enumerate(plot.iterrows()):
        status = bool(row["populist_in_pre_election_government"])
        ax.errorbar(
            row["ame"] * 100,
            index,
            xerr=[
                [100 * (row["ame"] - row["ame_low"])],
                [100 * (row["ame_high"] - row["ame"])],
            ],
            fmt="o",
            color=colors[status],
            ecolor=colors[status],
            capsize=3,
        )
    for status in (False, True):
        ax.scatter([], [], color=colors[status], label=labels[status])
    ax.axvline(0, color="#333333", linestyle="--", linewidth=1)
    ax.set_yticks(np.arange(len(plot)), plot["cntry"])
    ax.set_xlabel(
        "Effect of a 1-point increase in distrust on predicted populist-vote probability "
        "(percentage points)"
    )
    ax.set_title(
        "Political distrust and populist voting by country\n"
        "Colors show whether a populist party was in government before the election"
    )
    ax.legend(loc="lower right", frameon=True)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "stage9_h1_country_ame_by_government_context.png", dpi=180)
    plt.close(fig)


def write_report(context: pd.DataFrame, crosswalk: pd.DataFrame, effects: pd.DataFrame, slopes: pd.DataFrame, influence: pd.DataFrame, cells: pd.DataFrame, summaries: pd.DataFrame) -> None:
    interaction = effects.loc[effects["term"].str.contains(":")].iloc[0]
    unresolved = int(crosswalk["government_status"].eq("unresolved").sum())
    sparse_incumbent = int((cells["incumbent_populist"] < 30).sum())
    md = f"""# Stage 9B exploratory government/opposition context

Pre-election cabinet status is derived from [ParlGov 2024](https://doi.org/10.7910/DVN/2VZ5ZC), which covers elections and cabinets through June 2023. PopuList's published ParlGov and Party Facts identifiers provide the party crosswalk; no party-name matching is used. If an election immediately follows a caretaker cabinet, the most recent non-caretaker cabinet supplies partisan incumbent status and the caretaker is retained in the audit table.

## Country context

{markdown_table(context[['cntry', 'election_date', 'partisan_cabinet_name', 'populist_in_pre_election_government', 'incumbent_populist_parties']].fillna(''))}

## Context interaction

{markdown_table(slopes.round(3))}

![Government-context slopes](../figures/stage9_government_context_slopes.png)

The same comparison below retains every country as a separate point. Values to the
right of zero indicate that greater distrust is associated with a higher predicted
probability of populist voting; values to the left indicate the opposite pattern.

![Country H1 effects grouped by government context](../figures/stage9_country_effects_by_government_context.png)

For compact presentation, the following version keeps the original one-country-per-row
forest-plot layout and uses color only for pre-election government context.

![Country H1 effects colored by government context](../figures/stage9_h1_country_ame_by_government_context.png)

The interaction coefficient comparing H1 slopes in contexts with versus without a populist party in the pre-election government is {interaction['estimate_log_odds']:.3f} (95% interval {interaction['conf_low']:.3f} to {interaction['conf_high']:.3f}, p={interaction['p_value']:.3f}). This is an exploratory comparison across only 23 countries and cannot establish that government participation causes the slope difference.

Across leave-one-country-out refits, the interaction ranges from {influence['interaction_estimate'].min():.3f} to {influence['interaction_estimate'].max():.3f}; {int((influence['conf_high'] < 0).sum())} of 23 intervals remain entirely below zero. This reveals whether the contextual pattern is concentrated in one country without authorizing post-hoc exclusions.

## Party-level vote type

{markdown_table(summaries.round(3))}

The identifier crosswalk leaves {unresolved} populist party-response categories unresolved. A three-category multinomial model was not fitted: {sparse_incumbent} of the 23 country rows have fewer than 30 incumbent-populist voters, so category-specific estimates would combine structural zeros, sparse cells, and a different unweighted estimator. The auditable vote-type cells are retained for future design work rather than forcing an unstable model.

## Interpretation boundary

The context result is compatible with the idea that generic trust in parliament, politicians, and parties has a different political target when populists govern. It does not directly measure trust in incumbents or “the establishment.” The Stage 6 primary model remains unchanged, and Stage 9B is explicitly post-result and exploratory.
"""
    (REPORTS / "government_context.md").write_text(md, encoding="utf-8")
    rendered = markdown.markdown(md, extensions=["tables"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Stage 9B government context</title><style>body{{font:16px/1.5 system-ui;max-width:1100px;margin:auto;padding:2rem;color:#24303b}}h1,h2{{color:#16324f}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #dbe4ea;padding:.4rem}}th{{background:#16324f;color:white}}img{{max-width:100%}}code{{background:#eef2f5}}</style></head><body>{rendered}</body></html>"
    (REPORTS / "government_context.html").write_text(html, encoding="utf-8")


def main() -> None:
    for directory in (REPORTS, TABLES, FIGURES, PROCESSED):
        directory.mkdir(parents=True, exist_ok=True)
    mapping = pd.read_csv(PARTY_MAPPING, low_memory=False)
    populist = pd.read_csv(POPULIST, sep=";", low_memory=False)
    context = build_context(mapping, load_parlgov(), populist)
    crosswalk = party_crosswalk(mapping, populist, context)
    sample, countries = prepare_model_data(pd.read_csv(ANALYSIS_BASE, low_memory=False), context, crosswalk)
    effects, slopes = context_model(sample)
    influence = context_influence(sample)
    cells, summaries = vote_type_tables(sample)
    context.to_csv(PROCESSED / "stage9_government_context.csv", index=False)
    crosswalk.to_csv(PROCESSED / "stage9_party_government_crosswalk.csv", index=False)
    effects.to_csv(TABLES / "stage9_context_interaction_effects.csv", index=False)
    slopes.to_csv(TABLES / "stage9_context_slopes.csv", index=False)
    influence.to_csv(TABLES / "stage9_context_influence.csv", index=False)
    cells.to_csv(TABLES / "stage9_vote_type_cells.csv", index=False)
    summaries.to_csv(TABLES / "stage9_vote_type_summaries.csv", index=False)
    country_context = (
        pd.read_csv(TABLES / "stage9_country_effects.csv")
        .loc[lambda frame: frame["term"].eq("distrust_index_three")]
        .merge(
            context[["cntry", "populist_in_pre_election_government"]],
            on="cntry",
            how="left",
            validate="one_to_one",
        )
    )
    country_context.to_csv(TABLES / "stage9_country_context_effects.csv", index=False)
    make_figure(slopes)
    make_country_context_figure(country_context)
    make_context_colored_forest(country_context)
    write_report(context.loc[context["cntry"].isin(countries)], crosswalk, effects, slopes, influence, cells, summaries)
    print(f"Stage 9B: {len(countries)} countries; {crosswalk['government_status'].eq('unresolved').sum()} unresolved populist response categories")


if __name__ == "__main__":
    main()
