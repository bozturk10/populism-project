import pandas as pd
import pytest

from populism_project.outcomes import build_analysis_base, select_party_response


@pytest.fixture(scope="module")
def analysis_base():
    return build_analysis_base()


def test_table_c_integrity_and_primary_outcome_counts(analysis_base):
    data = analysis_base
    assert len(data) == 59_685
    assert data["respondent_key"].is_unique
    assert data["analysis_eligible"].sum() == 32_760
    assert data.loc[
        data["analysis_eligible"], "voted_populist"
    ].value_counts().to_dict() == {0: 25_481, 1: 7_279}
    assert data.loc[~data["vote_status"].eq("voted"), "voted_populist"].isna().all()


def test_slovenia_sd_correction_changes_only_the_binary_classification(analysis_base):
    slovenia = analysis_base[analysis_base["cntry"].eq("SI")]
    sd_voters = slovenia[
        slovenia["vote_status"].eq("voted")
        & slovenia["ess_variable"].eq("prtvtfsi")
        & slovenia["ess_party_code"].eq(6)
    ]
    assert len(sd_voters) == 77
    assert sd_voters["voted_populist"].eq(0).all()


def test_party_selection_rules_on_synthetic_rows():
    respondents = pd.DataFrame(
        {
            "cntry": ["AT", "DE", "LT", "LT", "LT"],
            "party_slot_1_variable": [
                "prtvtcat",
                "prtvfde1",
                "prtvclt1",
                "prtvclt1",
                "prtvclt1",
            ],
            "party_slot_1_raw_code": [3, 1, 5, 99, 99],
            "party_slot_2_variable": [
                pd.NA,
                "prtvfde2",
                "prtvclt2",
                "prtvclt2",
                "prtvclt2",
            ],
            "party_slot_2_raw_code": [pd.NA, 6, 99, 77, 99],
            "party_slot_3_variable": [
                pd.NA,
                pd.NA,
                "prtvclt3",
                "prtvclt3",
                "prtvclt3",
            ],
            "party_slot_3_raw_code": [pd.NA, pd.NA, 99, 99, 13],
        }
    )
    selected = select_party_response(respondents)
    assert selected["ess_variable"].tolist() == [
        "prtvtcat",
        "prtvfde2",
        "prtvclt1",
        "prtvclt2",
        "prtvclt3",
    ]
    assert selected["ess_party_code"].tolist() == [3, 6, 5, 77, 13]


def test_special_country_rules_hold_in_full_data(analysis_base):
    germany = analysis_base[analysis_base["cntry"].eq("DE")]
    lithuania = analysis_base[analysis_base["cntry"].eq("LT")]
    assert germany["ess_variable"].eq("prtvfde2").all()
    assert set(lithuania["ess_variable"].dropna()) == {
        "prtvclt1",
        "prtvclt2",
        "prtvclt3",
    }


def test_exclusion_counts_are_explicit_and_stable(analysis_base):
    counts = analysis_base["outcome_status"].value_counts().to_dict()
    assert counts["outside_coverage"] == 4_223
    assert counts["mixed_alliance"] == 66
    assert counts["unresolved_alliance"] == 2
    assert counts["party_independent_candidate"] == 125
    assert counts["party_other_unspecified"] == 944
    assert "unclassifiable_party" not in counts
    assert (
        analysis_base.loc[
            analysis_base["cntry"].isin(["IL", "ME", "MK", "RS"]),
            "analysis_eligible",
        ].sum()
        == 0
    )
