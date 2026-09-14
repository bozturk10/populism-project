import pandas as pd

from populism_project.parties import build_party_mapping, validate_party_mapping


def party(mapping: pd.DataFrame, country: str, variable: str, code: int) -> pd.Series:
    return mapping[
        mapping["cntry"].eq(country)
        & mapping["ess_variable"].eq(variable)
        & mapping["ess_party_code"].eq(code)
    ].iloc[0]


def test_mapping_covers_every_ess_category_and_observed_party():
    mapping = build_party_mapping()
    validate_party_mapping(mapping)
    assert len(mapping) == 627
    assert not mapping.duplicated(["cntry", "ess_variable", "ess_party_code"]).any()
    assert not (
        mapping["respondent_count"].gt(0)
        & mapping["response_status"].eq("party")
        & mapping["classification_source"].eq("unclassified")
    ).any()


def test_identifier_and_manual_identity_links_are_auditable():
    mapping = build_party_mapping()
    fpo = party(mapping, "AT", "prtvtcat", 3)
    belang = party(mapping, "BE", "prtvtebe", 6)
    assert (fpo["final_populist"], fpo["classification_source"]) == (1, "partyfacts_id")
    assert belang["final_populist"] == 1
    assert belang["manual_relationship"] == "rename_direct_successor"
    assert belang["manual_target_partyfacts_id"] == 553


def test_slovenian_social_democrats_do_not_inherit_united_left_classification():
    mapping = build_party_mapping()
    social_democrats = party(mapping, "SI", "prtvtfsi", 6)
    assert social_democrats["partyfacts_id"] == 1403
    assert social_democrats["populist_party_name"] == "Združena levica"
    classification = (
        social_democrats["final_populist"],
        social_democrats["final_borderline"],
    )
    assert classification == (
        0,
        0,
    )
    assert social_democrats["classification_source"] == "manual_identity"
    assert social_democrats["manual_relationship"] == "source_id_conflict"


def test_nonparties_and_mixed_alliance_are_not_rounded_to_zero():
    mapping = build_party_mapping()
    independent = party(mapping, "IE", "prtvtdie", 5)
    other = party(mapping, "FR", "prtvtefr", 12)
    mixed = party(mapping, "HR", "prtvtbhr", 5)
    assert pd.isna(independent["final_populist"])
    assert independent["response_status"] == "independent_candidate"
    assert pd.isna(other["final_populist"])
    assert other["response_status"] == "other_unspecified"
    assert pd.isna(mixed["final_populist"])
    assert mixed["alliance_status"] == "mixed_alliance"


def test_operational_zeros_borderline_rule_and_coverage_are_distinct():
    mapping = build_party_mapping()
    spo = party(mapping, "AT", "prtvtcat", 1)
    nva = party(mapping, "BE", "prtvtebe", 3)
    israel = mapping[mapping["cntry"].eq("IL")]
    assert (spo["final_populist"], spo["classification_source"]) == (
        0,
        "not_in_populist",
    )
    assert (nva["final_populist"], nva["final_borderline"]) == (0, 1)
    assert israel["final_populist"].isna().all()
