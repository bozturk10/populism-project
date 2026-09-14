import pandas as pd

from .config import ANALYSIS_BASE, PARTY_MAPPING, PROCESSED, RESPONDENT_BASE
from .parties import OUTSIDE_COVERAGE

JOIN_KEY = ["cntry", "ess_variable", "ess_party_code"]
PARTY_FIELDS = [
    *JOIN_KEY,
    "ess_party_label",
    "partyfacts_id",
    "name_english",
    "populist_party_name",
    "populist_party_name_english",
    "populist_parlgov_id",
    "final_populist",
    "final_borderline",
    "classification_source",
    "alliance_status",
    "manual_relationship",
    "manual_target_partyfacts_id",
    "manual_target_party",
    "manual_evidence",
    "election_date",
    "response_status",
]


def select_party_response(respondents: pd.DataFrame) -> pd.DataFrame:
    selected = pd.DataFrame(index=respondents.index)
    selected["ess_variable"] = respondents["party_slot_1_variable"]
    selected["ess_party_code"] = pd.to_numeric(
        respondents["party_slot_1_raw_code"], errors="coerce"
    ).astype("Float64")

    germany = respondents["cntry"].eq("DE")
    selected.loc[germany, "ess_variable"] = respondents.loc[
        germany, "party_slot_2_variable"
    ]
    selected.loc[germany, "ess_party_code"] = pd.to_numeric(
        respondents.loc[germany, "party_slot_2_raw_code"], errors="coerce"
    ).astype("Float64")

    lithuania = respondents["cntry"].eq("LT")
    selected.loc[lithuania, ["ess_variable", "ess_party_code"]] = pd.NA
    for slot in range(1, 4):
        variable = respondents[f"party_slot_{slot}_variable"]
        code = pd.to_numeric(
            respondents[f"party_slot_{slot}_raw_code"], errors="coerce"
        ).astype("Float64")
        routed = lithuania & selected["ess_party_code"].isna() & code.ne(99)
        selected.loc[routed, "ess_variable"] = variable[routed]
        selected.loc[routed, "ess_party_code"] = code[routed]
    no_route = lithuania & selected["ess_party_code"].isna()
    selected.loc[no_route, "ess_variable"] = respondents.loc[
        no_route, "party_slot_1_variable"
    ]
    selected.loc[no_route, "ess_party_code"] = pd.to_numeric(
        respondents.loc[no_route, "party_slot_1_raw_code"], errors="coerce"
    ).astype("Float64")
    return selected


def outcome_status(data: pd.DataFrame) -> pd.Series:
    status = data["vote_status"].copy()
    voted = data["vote_status"].eq("voted")
    status.loc[voted & data["final_populist"].eq(1)] = "populist_voter"
    status.loc[voted & data["final_populist"].eq(0)] = "non_populist_voter"
    unclassified = voted & data["final_populist"].isna()
    status.loc[unclassified] = "unclassifiable_party"
    special = unclassified & ~data["response_status"].eq("party")
    status.loc[special] = "party_" + data.loc[special, "response_status"]
    independent = unclassified & data["manual_relationship"].eq("not_a_party")
    status.loc[independent] = "party_independent_candidate"
    outside = unclassified & data["cntry"].isin(OUTSIDE_COVERAGE)
    status.loc[outside] = "outside_coverage"
    status.loc[unclassified & data["alliance_status"].eq("mixed_alliance")] = (
        "mixed_alliance"
    )
    status.loc[unclassified & data["alliance_status"].eq("unresolved_alliance")] = (
        "unresolved_alliance"
    )
    return status.astype("string")


def build_analysis_base() -> pd.DataFrame:
    respondents = pd.read_csv(RESPONDENT_BASE, low_memory=False)
    mapping = pd.read_csv(PARTY_MAPPING, low_memory=False)[PARTY_FIELDS]
    selected = select_party_response(respondents)
    data = respondents.join(selected)
    data = data.merge(mapping, on=JOIN_KEY, how="left", validate="many_to_one")
    voted = data["vote_status"].eq("voted")
    outcomes = pd.DataFrame(index=data.index)
    outcomes["voted_populist"] = data["final_populist"].where(voted).astype("Int64")
    outcomes["voted_borderline"] = data["final_borderline"].where(voted).astype("Int64")
    outcomes["outcome_status"] = outcome_status(data)
    outcomes["analysis_eligible"] = voted & outcomes["voted_populist"].notna()
    data = pd.concat([data, outcomes], axis=1)
    validate_analysis_base(data)
    return data


def validate_analysis_base(data: pd.DataFrame) -> None:
    if len(data) != 59_685 or not data["respondent_key"].is_unique:
        raise ValueError("Table C must retain one row per Table A respondent")
    if data.loc[~data["vote_status"].eq("voted"), "voted_populist"].notna().any():
        raise ValueError("Non-voters cannot receive a party-vote outcome")
    eligible = data["analysis_eligible"]
    if data.loc[eligible, JOIN_KEY].isna().any().any():
        raise ValueError("Eligible voters require a complete party mapping key")
    if not data.loc[eligible, "voted_populist"].isin([0, 1]).all():
        raise ValueError("Eligible voters require a binary outcome")


def write_analysis_base() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = build_analysis_base()
    data.to_csv(ANALYSIS_BASE, index=False)
    country = _country_summary(data)
    country.to_csv(PROCESSED / "ess10_outcome_by_country.csv", index=False)
    _write_flow_report(data, country)
    return data, country


def _country_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country, group in data.groupby("cntry", sort=True):
        eligible = group["analysis_eligible"]
        populist = eligible & group["voted_populist"].eq(1)
        rows.append(
            {
                "cntry": country,
                "respondents": len(group),
                "reported_voters": int(group["vote_status"].eq("voted").sum()),
                "classifiable_voters": int(eligible.sum()),
                "populist_voters": int(populist.sum()),
                "non_populist_voters": int((eligible & ~populist).sum()),
                "populist_share": group.loc[eligible, "voted_populist"].mean(),
            }
        )
    return pd.DataFrame(rows)


def _write_flow_report(data: pd.DataFrame, country: pd.DataFrame) -> None:
    statuses = data["outcome_status"].value_counts(dropna=False)
    sample_size = int(data["analysis_eligible"].sum())
    covered = ~data["cntry"].isin(OUTSIDE_COVERAGE)
    voters = covered & data["vote_status"].eq("voted")
    party_response = voters & data["response_status"].eq("party")
    resolved = party_response & ~data["alliance_status"].isin(
        ["mixed_alliance", "unresolved_alliance"]
    )
    stages = [
        ("All ESS respondents", pd.Series(True, index=data.index)),
        ("Country covered by PopuList", covered),
        ("Reported voting", voters),
        ("Identified party response", party_response),
        ("Resolved party or alliance", resolved),
        ("Classifiable primary outcome", data["analysis_eligible"]),
    ]
    rows = [
        "# ESS Round 10 outcome construction",
        "",
        "## Sequential sample flow",
        "",
        "| Stage | Retained | Dropped at stage |",
        "|---|---:|---:|",
    ]
    previous = len(data)
    for label, mask in stages:
        retained = int(mask.sum())
        rows.append(f"| {label} | {retained:,} | {previous - retained:,} |")
        previous = retained
    rows.extend(
        [
            "",
            "## Final outcome status",
            "",
            "| Outcome status | Respondents |",
            "|---|---:|",
            *[f"| {status} | {count:,} |" for status, count in statuses.items()],
            "",
            f"Primary analysis sample: {sample_size:,} respondents.",
            "",
            "## Country validation",
            "",
            "| Country | Voters | Classifiable | Populist | Non-populist | Share |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in country.itertuples():
        share = "" if pd.isna(row.populist_share) else f"{row.populist_share:.3f}"
        rows.append(
            f"| {row.cntry} | {row.reported_voters:,} | "
            f"{row.classifiable_voters:,} | {row.populist_voters:,} | "
            f"{row.non_populist_voters:,} | {share} |"
        )
    (PROCESSED / "ess10_outcome_flow.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
