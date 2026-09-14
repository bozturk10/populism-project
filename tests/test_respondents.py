import pandas as pd

from populism_project.codebooks import Variable
from populism_project.respondents import (
    build_respondent_base,
    construct_key,
    recode,
    validate_respondent_base,
    vote_status,
)


def test_key_construction_and_status():
    frame = pd.DataFrame({"cntry": ["GB", "DE"], "idno": [1, 22]})
    assert construct_key(frame).tolist() == ["ESS10-GB-1", "ESS10-DE-22"]
    assert vote_status(pd.Series([1, 2, 3, 7, 8, 9])).tolist() == [
        "voted",
        "non_voter",
        "ineligible",
        "refusal",
        "dont_know",
        "no_answer",
    ]


def test_variable_specific_missing_recode_preserves_valid_scale_values():
    spec = Variable("x", "", "", {}, frozenset({77, 88, 99}))
    result = recode(pd.Series([7, 8, 9, 77, 88, 99]), spec)
    assert result.iloc[:3].tolist() == [7.0, 8.0, 9.0]
    assert result.iloc[3:].isna().all()


def test_full_concatenation_counts_and_no_key_overlap():
    frame = build_respondent_base()
    validate_respondent_base(frame)
    by_source = frame.groupby("source_dataset")["respondent_key"].agg(set)
    assert by_source.iloc[0].isdisjoint(by_source.iloc[1])
    assert {
        "ppltrst",
        "trstprl",
        "trstlgl",
        "trstplc",
        "trstplt",
        "trstprt",
        "trstep",
        "trstun",
        "trstsci",
        "votedir",
    }.issubset(frame.columns)
