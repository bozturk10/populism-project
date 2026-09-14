import pandas as pd

from .codebooks import parse_codebook, party_variables
from .config import (
    ALLIANCE_RULES,
    ESS_CODEBOOKS,
    PARTY_OVERRIDES,
    PARTYFACTS_ESS_ALL,
    POPULIST,
    PROCESSED,
)

ELECTIONS = {
    "AT": "2019-09-29",
    "BE": "2019-05-26",
    "BG": "2021-04-04",
    "CH": "2019-10-20",
    "CY": "2021-05-30",
    "CZ": "2017-10-21",
    "DE": "2017-09-24",
    "EE": "2019-03-03",
    "ES": "2019-11-10",
    "FI": "2019-04-14",
    "FR": "2017-06-18",
    "GB": "2019-12-12",
    "GR": "2019-07-07",
    "HR": "2020-07-05",
    "HU": "2018-04-08",
    "IE": "2020-02-08",
    "IL": "2021-03-23",
    "IS": "2017-10-28",
    "IT": "2018-03-04",
    "LT": "2020-10-25",
    "LV": "2018-10-06",
    "ME": "2020-08-30",
    "MK": "2020-07-15",
    "NL": "2021-03-17",
    "NO": "2021-09-13",
    "PL": "2019-10-13",
    "PT": "2019-10-06",
    "RS": "2020-06-21",
    "SE": "2018-09-09",
    "SI": "2018-06-03",
    "SK": "2020-02-29",
}
OUTSIDE_COVERAGE = {"IL", "ME", "MK", "RS"}
KEY = ["cntry", "ess_variable", "ess_party_code"]


def load_partyfacts() -> pd.DataFrame:
    data = pd.read_csv(PARTYFACTS_ESS_ALL)
    data = data[data["essround"].eq(10) & data["ess_variable"].str.startswith("prtv")]
    return data.rename(columns={"ess_cntry": "cntry", "ess_party_id": "ess_party_code"})


def extract_categories() -> pd.DataFrame:
    partyfacts = load_partyfacts()
    countries = partyfacts.groupby("ess_variable")["cntry"].first().to_dict()
    rows = []
    for path in ESS_CODEBOOKS.values():
        for name, variable in party_variables(parse_codebook(path)).items():
            for code, label in variable.values.items():
                status = "party"
                if code in variable.missing_codes:
                    status = "missing"
                elif label.casefold().startswith("other"):
                    status = "other_unspecified"
                elif "invalid" in label.casefold() or "blank" in label.casefold():
                    status = "invalid"
                rows.append(
                    {
                        "cntry": countries[name],
                        "ess_variable": name,
                        "ess_party_code": code,
                        "ess_party_label": label,
                        "response_status": status,
                    }
                )
    return pd.DataFrame(rows).sort_values(KEY, ignore_index=True)


def _respondent_counts(categories: pd.DataFrame) -> pd.Series:
    respondents = pd.read_csv(PROCESSED / "ess10_respondent_base.csv", low_memory=False)
    counts = []
    for row in categories.itertuples():
        column = f"{row.ess_variable}_raw"
        counts.append(int(respondents[column].eq(row.ess_party_code).sum()))
    return pd.Series(counts, index=categories.index)


def _join_sources(categories: pd.DataFrame) -> pd.DataFrame:
    partyfacts = load_partyfacts().drop(columns=["essround"])
    data = categories.merge(partyfacts, on=KEY, how="left", validate="one_to_one")
    populist = pd.read_csv(POPULIST, sep=";")
    linked = populist[populist["partyfacts_id"].notna()].copy()
    linked = linked[~linked["partyfacts_id"].duplicated(keep=False)]
    linked = linked.rename(
        columns={column: f"populist_{column}" for column in linked.columns}
    )
    return data.merge(
        linked,
        left_on="partyfacts_id",
        right_on="populist_partyfacts_id",
        how="left",
        validate="many_to_one",
    )


def _classify(data: pd.DataFrame) -> pd.DataFrame:
    data.loc[data["technical"].eq(7), "response_status"] = "other_unspecified"
    data.loc[data["technical"].eq(8), "response_status"] = "independent_candidate"
    data.loc[data["technical"].eq(12), "response_status"] = "invalid"
    data["election_date"] = data["cntry"].map(ELECTIONS)
    year = pd.to_datetime(data["election_date"]).dt.year
    direct = data["populist_party_name"].notna()
    firm = (
        direct
        & data["populist_populist"].eq(1)
        & year.between(
            data["populist_populist_startnobl"],
            data["populist_populist_endnobl"],
        )
    )
    borderline = (
        direct
        & data["populist_populist_bl"].eq(1)
        & year.between(data["populist_populist_start"], data["populist_populist_end"])
    )
    party = data["response_status"].eq("party")
    identified = data["partyfacts_id"].notna()
    covered = ~data["cntry"].isin(OUTSIDE_COVERAGE)
    data["final_populist"] = pd.Series(pd.NA, index=data.index, dtype="Int64")
    data["final_borderline"] = pd.Series(0, index=data.index, dtype="Int64")
    data["classification_source"] = "unclassified"
    operational = party & identified & covered & ~direct
    data.loc[operational, "final_populist"] = 0
    data.loc[operational, "classification_source"] = "not_in_populist"
    data.loc[party & direct, "final_populist"] = 0
    data.loc[firm, "final_populist"] = 1
    data.loc[borderline, "final_borderline"] = 1
    data.loc[party & direct, "classification_source"] = "partyfacts_id"
    data.loc[party & ~covered, "classification_source"] = "outside_coverage"
    data.loc[~party, "classification_source"] = data.loc[~party, "response_status"]
    return data


def _apply_manual_rules(data: pd.DataFrame) -> pd.DataFrame:
    overrides = pd.read_csv(PARTY_OVERRIDES)
    alliances = pd.read_csv(ALLIANCE_RULES)
    for rules, source in [
        (overrides, "manual_identity"),
        (alliances, "manual_alliance"),
    ]:
        rules = rules.rename(columns={"ess_party_code": "ess_party_code_rule"})
        for rule in rules.itertuples():
            mask = (
                data["cntry"].eq(rule.cntry)
                & data["ess_variable"].eq(rule.ess_variable)
                & data["ess_party_code"].eq(rule.ess_party_code_rule)
            )
            if mask.sum() != 1:
                raise ValueError(f"Manual rule does not match one ESS row: {rule}")
            data.loc[mask, "final_populist"] = rule.final_populist
            data.loc[mask, "final_borderline"] = rule.final_borderline
            data.loc[mask, "classification_source"] = source
            data.loc[mask, "manual_evidence"] = rule.evidence
            if source == "manual_identity":
                data.loc[mask, "manual_relationship"] = rule.relationship
                data.loc[mask, "manual_target_partyfacts_id"] = (
                    rule.target_partyfacts_id
                )
                data.loc[mask, "manual_target_party"] = rule.target_populist_party
            else:
                data.loc[mask, "alliance_status"] = rule.alliance_status
    return data


def build_party_mapping() -> pd.DataFrame:
    categories = extract_categories()
    categories["respondent_count"] = _respondent_counts(categories)
    data = _apply_manual_rules(_classify(_join_sources(categories)))
    data["include_primary"] = data["final_populist"].notna()
    validate_party_mapping(data)
    front = [
        *KEY,
        "ess_party_label",
        "respondent_count",
        "partyfacts_id",
        "name_english",
        "populist_party_name",
        "final_populist",
        "final_borderline",
        "classification_source",
        "alliance_status",
        "manual_relationship",
        "manual_target_partyfacts_id",
        "manual_target_party",
        "include_primary",
        "election_date",
    ]
    return data[front + [column for column in data if column not in front]]


def validate_party_mapping(data: pd.DataFrame) -> None:
    if len(data) != 627 or data.duplicated(KEY).any():
        raise ValueError("Expected 627 unique ESS party-code rows")
    observed_parties = data["respondent_count"].gt(0) & data["response_status"].eq(
        "party"
    )
    unresolved = observed_parties & data["classification_source"].eq("unclassified")
    if unresolved.any():
        raise ValueError("Observed party responses remain unresolved")
    if data.loc[data["cntry"].isin(OUTSIDE_COVERAGE), "final_populist"].notna().any():
        raise ValueError("Countries outside PopuList coverage must remain unclassified")


def write_party_mapping() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = build_party_mapping()
    exceptions = data[
        data["classification_source"].str.startswith("manual")
        | data["final_populist"].isna()
        | (data["respondent_count"].eq(0) & data["partyfacts_id"].isna())
    ].copy()
    data.to_csv(PROCESSED / "ess10_party_mapping.csv", index=False)
    exceptions.to_csv(PROCESSED / "ess10_party_exceptions.csv", index=False)
    _write_validation_report(data, exceptions)
    return data, exceptions


def _write_validation_report(data: pd.DataFrame, exceptions: pd.DataFrame) -> None:
    unresolved = (
        data["respondent_count"].gt(0)
        & data["response_status"].eq("party")
        & data["classification_source"].eq("unclassified")
    )
    rows = [
        "# ESS Round 10 party-mapping validation",
        "",
        f"- Party-code rows: {len(data):,}",
        f"- Documented exception rows: {len(exceptions):,}",
        f"- Respondents represented: {data['respondent_count'].sum():,}",
        f"- Observed party rows left unresolved: {int(unresolved.sum())}",
        "",
        "## Primary classification",
        "",
        "| Value | Party-code rows | Respondents |",
        "|---|---:|---:|",
    ]
    for value, label in [(1, "Populist"), (0, "Non-populist"), (pd.NA, "Excluded")]:
        mask = (
            data["final_populist"].isna()
            if pd.isna(value)
            else data["final_populist"].eq(value)
        )
        count = int(data.loc[mask, "respondent_count"].sum())
        rows.append(f"| {label} | {int(mask.sum()):,} | {count:,} |")
    rows.extend(
        [
            "",
            "Manual decisions are stored in `data/manual/party_overrides.csv` and "
            "`data/manual/alliance_rules.csv`. Mixed alliances, non-party answers, "
            "unresolved identities, and countries outside PopuList coverage remain "
            "excluded.",
        ]
    )
    (PROCESSED / "ess10_party_validation.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
